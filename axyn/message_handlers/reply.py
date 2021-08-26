import asyncio
import logging
import random

import discord
from logdecorator import log_on_end, log_on_start
from logdecorator.asyncio import async_log_on_end, async_log_on_start

from axyn.filters import reason_not_to_reply
from axyn.interval import quantile_interval
from axyn.message_handlers import MessageHandler
from axyn.preprocessor import preprocess
from axyn.privacy import filter_responses


class Reply(MessageHandler):
    async def handle(self):
        """Respond to this message, if allowed."""

        reason = reason_not_to_reply(self.client, self.message)
        if reason:
            return False

        delay = await self._get_reply_delay()
        if delay > 0:
            await asyncio.sleep(delay)

        await self._process_reply()

    async def _process_reply(self):
        """Respond to this message immediately, if distance permits."""

        async with self.message.channel.typing():
            reply, distance = self._get_reply()

        acceptable_distance = self._get_distance_threshold()

        if reply and distance <= acceptable_distance:
            await self._send_reply(reply)

    def _is_direct(self):
        """Return whether this message is directly talking to Axyn."""

        return (
            self.message.channel.type == discord.ChannelType.private
            or self.client.user.mentioned_in(self.message)
            or (
                self.message.reference
                and self.message.reference.resolved
                and self.message.reference.resolved.author == self.client.user
            )
            or "axyn" in self.message.channel.name
        )

    @async_log_on_end(logging.INFO, "Delaying reply by {result} seconds")
    async def _get_reply_delay(self):
        """Return number of seconds to wait before replying to this message."""

        if self._is_direct():
            return 0

        interval = await quantile_interval(
            self.client, self.message.channel, quantile=0.5, default=60
        )

        return max(interval * 1.5, 180)

    @log_on_end(logging.INFO, "The distance threshold is {result}")
    def _get_distance_threshold(self):
        """Return the maximum acceptible distance for replies to this message."""

        if self._is_direct():
            return float("inf")
        else:
            return 1.5

    @log_on_start(logging.DEBUG, 'Getting reply to "{self.message.clean_content}"')
    @log_on_end(logging.INFO, 'Selected reply "{result[0]}" at distance {result[1]}')
    def _get_reply(self):
        """Return the chosen reply, and its distance, for this message."""

        content = preprocess(self.client, self.message)
        responses, distance = self.client.message_responder.get_all_responses(content)

        filtered_responses = filter_responses(
            self.client, responses, self.message.channel
        )

        if filtered_responses:
            reply = random.choice(filtered_responses).text
            return reply, distance

        return None, float("inf")

    @async_log_on_start(logging.INFO, 'Sending reply "{reply}"')
    async def _send_reply(self, reply):
        """Send a reply message."""

        await self.message.channel.send(reply)
