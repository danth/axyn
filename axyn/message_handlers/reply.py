import asyncio
from logging import INFO, DEBUG, getLogger
from random import random, shuffle
from statistics import StatisticsError
from typing import Optional

from logdecorator import log_on_start, log_on_end
from logdecorator.asyncio import async_log_on_start, async_log_on_end

from axyn.channel import channel_members
from axyn.database import ChannelRecord, MessageRevisionRecord
from axyn.filters import reason_not_to_reply, is_direct
from axyn.history import get_history, get_delays
from axyn.message_handlers import MessageHandler
from axyn.preprocessor import preprocess
from axyn.privacy import can_send_in_channel


class Reply(MessageHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._logger = getLogger(__name__)

    async def handle(self):
        """Respond to this message, if allowed."""

        reason = reason_not_to_reply(self.message)
        if reason:
            self._logger.debug(f"Not replying because {reason}")
            return

        if random() > self._get_reply_probability():
            self._logger.debug("Not replying because the probability check failed")
            return

        delay = await self._get_reply_delay()
        if delay > 0:
            await asyncio.sleep(delay)

        await self._process_reply()

    async def _process_reply(self):
        """Respond to this message immediately."""

        async with self.message.channel.typing():
            reply, distance = await self._get_reply()

        if reply:
            maximum_distance = self._get_maximum_distance()

            if distance <= maximum_distance:
                await self._send_reply(reply)

    @log_on_end(DEBUG, "Will reply with probability {result}")
    def _get_reply_probability(self) -> float:
        """Return the probability of attempting a reply."""

        if is_direct(self.client, self.message):
            return 1

        member_count = len(channel_members(self.message.channel))
        return 1 / (member_count - 1)

    @async_log_on_end(DEBUG, "Will reply in {result} seconds")
    async def _get_reply_delay(self) -> float:
        """Return the number of seconds to wait before attempting a reply."""

        if is_direct(self.client, self.message):
            return 0

        async with self.client.database_manager.session() as session:
            history = await get_history(session, self.message.channel.id)

            try:
                _, median, _ = await get_delays(session, history)
            except StatisticsError:
                median = 60

        return median * 1.5

    @log_on_end(DEBUG, "Will reply if cosine distance is below {result}")
    def _get_maximum_distance(self) -> float:
        """Return the maximum acceptable cosine distance for a reply to be sent."""

        if is_direct(self.client, self.message):
            # The maximum possible: so always reply.
            return 2

        return 0.1

    @log_on_start(DEBUG, 'Getting reply to "{self.message.clean_content}"')
    async def _get_reply(self) -> tuple[Optional[str], float]:
        """Return a chosen reply and its cosine distance."""

        async with self.client.database_manager.session() as session:
            responses, distance = await self.client.index_manager.get_responses(
                self.message.content,
                session,
            )

            shuffle(responses)

            # Select the first (after shuffling) response that we are allowed to use.
            for response in responses:
                await session.refresh(response, ["message"])

                if can_send_in_channel(self.client, response.message, self.message.channel):
                    self._logger.debug(f'Selected reply "{response.content}" with cosine distance {distance}')
                    text = preprocess(self.client, response.content)
                    return text, distance
                else:
                    self._logger.debug(f'Cannot use reply "{response.content}" due to privacy filter')

        self._logger.debug(f'Found no suitable replies')
        return None, float("inf")

    @async_log_on_start(INFO, 'Sending reply "{reply}"')
    async def _send_reply(self, reply):
        """Send a reply message."""

        await self.message.channel.send(
            reply,
            reference=self.message,
            mention_author=True,
        )

        # We need to store Axyn's own messages so that they appear in the
        # history as a prompt for whatever the user sends next.
        with self.client.database_manager.session() as session:
            session.merge(MessageRevisionRecord.from_message(reply))

