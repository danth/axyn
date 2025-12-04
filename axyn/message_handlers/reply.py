from __future__ import annotations
import asyncio
from axyn.channel import channel_members
from axyn.database import MessageRecord
from axyn.filters import reason_not_to_reply, is_direct
from axyn.history import get_history, get_delays
from axyn.message_handlers import MessageHandler
from axyn.preprocessor import preprocess_reply
from axyn.privacy import can_send_in_channel
from logging import getLogger
from random import random, shuffle
from statistics import StatisticsError
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from discord import Message
    from typing import Optional


class Reply(MessageHandler):
    def __init__(self, client: AxynClient, message: Message):
        super().__init__(client, message)

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

        async with self._channel.typing():
            reply, distance = await self._get_reply()

        if reply:
            maximum_distance = self._get_maximum_distance()

            if distance <= maximum_distance:
                await self._send_reply(reply)

    def _get_reply_probability(self) -> float:
        """Return the probability of attempting a reply."""

        if is_direct(self.client, self.message):
            self._logger.debug("Will reply with guaranteed probability")
            return 1

        member_count = len(channel_members(self._channel))

        probability = 1 / (member_count - 1)

        self._logger.debug(f"Will reply with probability {probability}")
        return probability

    async def _get_reply_delay(self) -> float:
        """Return the number of seconds to wait before attempting a reply."""

        if is_direct(self.client, self.message):
            self._logger.debug("Will reply immediately")
            return 0

        async with self.client.database_manager.read_session() as session:
            history = await get_history(session, self._channel.id)
            history = list(history)

            try:
                _, median, _ = await get_delays(session, history)
            except StatisticsError:
                median = 60

        delay = median * 1.5

        self._logger.debug(f"Will reply in {delay} seconds")
        return delay

    def _get_maximum_distance(self) -> float:
        """Return the maximum acceptable cosine distance for a reply to be sent."""

        if is_direct(self.client, self.message):
            self._logger.debug("Will reply regardless of cosine distance")
            return 2

        self._logger.debug("Will reply if cosine distance is below 0.1")
        return 0.1

    async def _get_reply(self) -> tuple[Optional[str], float]:
        """Return a chosen reply and its cosine distance."""

        async with self.client.database_manager.read_session() as session:
            groups = self.client.index_manager.get_response_groups(
                self.message.content,
                session,
            )

            async for responses, distance in groups:
                self._logger.debug(f"Processing response group with cosine distance {distance}")

                responses = list(responses)
                shuffle(responses)

                for response in responses:
                    original_response = await session.get_one(
                        MessageRecord,
                        response.message_id,
                    )

                    can_send = await can_send_in_channel(
                        self.client,
                        original_response,
                        self._channel,
                    )

                    if not can_send:
                        self._logger.debug(f'Cannot use reply "{response.content}" due to privacy filter')
                        continue

                    original_prompt = await self.client.index_manager.get_prompt_message(
                        session,
                        original_response,
                    )

                    if original_prompt is None:
                        self._logger.debug(f'Cannot use reply "{response.content}" because the original prompt is no longer valid')
                        continue

                    self._logger.debug(f'Selected reply "{response.content}"')

                    text = preprocess_reply(
                        response.content,
                        original_prompt_author_id=original_prompt.author_id,
                        original_response_author_id=original_response.author_id,
                        current_prompt_author_id=self.message.author.id,
                        axyn_id=self.client.axyn().id,
                    )

                    return text, distance

        self._logger.debug(f'Found no suitable responses')
        return None, float("inf")

    async def _send_reply(self, reply: str):
        """Send a reply message."""

        self._logger.info(f'Sending reply "{reply}"')

        await self._channel.send(
            reply,
            reference=self.message,
            mention_author=True,
        )

