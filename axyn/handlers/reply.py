from __future__ import annotations
from asyncio import create_task, sleep, timeout
from axyn.channel import channel_members
from axyn.database import MessageRecord
from axyn.filters import reason_not_to_reply, is_direct
from axyn.handlers import Handler
from axyn.preprocessor import preprocess_reply
from axyn.privacy import can_send_in_channel
from datetime import datetime, timedelta, timezone
from logging import getLogger
from random import random, shuffle
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from discord import Message
    from typing import Optional


class ReplyHandler(Handler):
    def __init__(self, client: AxynClient, message: Message):
        super().__init__(client, message)

        self._logger = getLogger(__name__)

    async def handle(self):
        """Respond to this message, if allowed."""

        reason = reason_not_to_reply(self.message)
        if reason:
            self._logger.debug(f"Not replying because {reason}")
            return

        reply, distance = await self._get_reply()

        if reply is None:
            return

        if random() > await self._get_probability(distance):
            self._logger.debug("Not replying because the probability check failed")
            return

        self._schedule_reply(reply)

    async def _get_probability(self, distance: float) -> float:
        """Return the probability of sending a reply."""

        if await is_direct(self.client, self.message):
            self._logger.debug("Probability of replying to a direct message is constant")
            return 1

        members = len(channel_members(self._channel)) - 1

        # https://www.desmos.com/calculator/jqyrqevoad
        probability = (2 - distance) / (2 * members * (distance + 1))

        self._logger.debug(f"Probability of replying is {probability}")
        return probability

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

    def _schedule_reply(self, reply: str):
        """
        Schedule the given reply to be sent soon.

        The reply will normally be sent after a few seconds. If during that
        time, the prompt author starts typing another message, the delay will
        be extended until they stop.

        If during the delay, another reply is scheduled with the same channel
        and prompt author, then this reply will be discarded. This particular
        key was chosen because:

        - Keeping channels separate means that high traffic elsewhere does not
          reduce the number of replies seen.
        - Keeping users separate mimics a human replying to a few messages they
          found interesting, rather than only the most recent message, which
          makes the fact that replies can be cancelled less obvious.
        - Cancelling replies to the same user avoids amplifying spam, because
          if they message too fast, then we will discard most of our replies
          before they are sent.
        """

        key = (self.message.author.id, self.message.channel.id)

        if task := self.client.reply_tasks.get(key):
            if not task.done():
                self._logger.info(f"Cancelling existing scheduled reply")
                task.cancel()

        self._logger.info(f'Scheduling reply "{reply}"')
        task = create_task(self._do_reply(reply))
        self.client.reply_tasks[key] = task

    async def _do_reply(self, reply: str):
        """
        Wait for a short length of time, then send the given reply.

        If during the delay, the prompt author starts typing another message,
        the delay will be extended until they stop. If we are waiting for an
        excessive length of time then the reply will be discarded.
        """

        async with self._channel.typing():
            try:
                async with timeout(30):
                    await self._delay_reply()
            except TimeoutError:
                self._logger.info("Cancelling scheduled reply because the user is typing")
                return

        await self._send_reply(reply)

    async def _delay_reply(self):
        """
        Wait for a short length of time.

        If during the delay, the prompt author starts typing another message,
        the delay will be extended until they stop.
        """

        delay = 2

        while delay > 0:
            await sleep(delay)

            try:
                last_typing = self.client.last_typing[self.message.author.id]
            except KeyError:
                break

            typing_until = last_typing + timedelta(seconds=10)
            delay = typing_until - datetime.now(timezone.utc)
            delay = delay.total_seconds()

    async def _send_reply(self, reply: str):
        """Send the given reply."""

        self._logger.info(f'Sending reply "{reply}"')

        await self._channel.send(
            reply,
            reference=self.message,
            mention_author=True,
        )

