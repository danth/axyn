from __future__ import annotations
import asyncio
from axyn.channel import channel_members
from axyn.database import MessageRecord
from axyn.filters import reason_not_to_reply, is_direct
from axyn.history import get_history, get_delays
from axyn.handlers import Handler
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

        if random() > self._get_probability(distance):
            self._logger.debug("Not replying because the probability check failed")
            return

        delay = await self._get_delay()
        if delay > 0:
            await asyncio.sleep(delay)

        await self._send_reply(reply)

    def _get_probability(self, distance: float) -> float:
        """Return the probability of sending a reply."""

        if is_direct(self.client, self.message):
            members = 1
        else:
            members = len(channel_members(self._channel)) - 1

        # https://www.desmos.com/calculator/jqyrqevoad
        probability = (2 - distance) / (2 * members * (distance + 1))

        self._logger.debug(f"Probability of replying is {probability}")
        return probability

    async def _get_delay(self) -> float:
        """Return the number of seconds to wait before sending a reply."""

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

