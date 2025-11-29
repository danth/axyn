import asyncio
import logging
import random
from statistics import StatisticsError

from logdecorator import log_on_end
from logdecorator.asyncio import async_log_on_end, async_log_on_start

from axyn.database import ChannelRecord, MessageRevisionRecord
from axyn.filters import reason_not_to_reply, is_direct
from axyn.history import get_history, get_delays
from axyn.message_handlers import MessageHandler
from axyn.preprocessor import preprocess
from axyn.privacy import filter_responses


class Reply(MessageHandler):
    async def handle(self):
        """Respond to this message, if allowed."""

        reason = reason_not_to_reply(self.message)
        if reason:
            return

        delay = await self._get_reply_delay()
        if delay > 0:
            await asyncio.sleep(delay)

        await self._process_reply()

    async def _process_reply(self):
        """Respond to this message immediately, if distance permits."""

        async with self.message.channel.typing():
            reply, distance = await self._get_reply()

        acceptable_distance = self._get_distance_threshold()

        if reply and distance <= acceptable_distance:
            await self._send_reply(reply)

    @async_log_on_end(logging.INFO, "Delaying reply by {result} seconds")
    async def _get_reply_delay(self):
        """Return number of seconds to wait before replying to this message."""

        if is_direct(self.client, self.message):
            return 0

        channel = ChannelRecord.from_channel(self.message.channel)

        with self.client.database_manager.session() as session:
            try:
                _, median, _ = get_delays(get_history(session, channel))
            except StatisticsError:
                median = 60

        return max(median * 1.5, 180)

    @log_on_end(logging.INFO, "The distance threshold is {result}")
    def _get_distance_threshold(self):
        """Return the maximum acceptible distance for replies to this message."""

        if is_direct(self.client, self.message):
            return float("inf")
        else:
            return 1.5

    @async_log_on_start(logging.DEBUG, 'Getting reply to "{self.message.clean_content}"')
    @async_log_on_end(logging.INFO, 'Selected reply "{result[0]}" at distance {result[1]}')
    async def _get_reply(self):
        """Return the chosen reply, and its distance, for this message."""

        with self.client.database_manager.session() as session:
            responses, distance = await self.client.index_manager.get_responses(
                self.message.content,
                session,
            )

            filtered_responses = filter_responses(
                self.client, responses, self.message.channel
            )

            if filtered_responses:
                reply = random.choice(filtered_responses).content
                reply = preprocess(self.client, reply)
                return reply, distance

        return None, float("inf")

    @async_log_on_start(logging.INFO, 'Sending reply "{reply}"')
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

