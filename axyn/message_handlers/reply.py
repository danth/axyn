import asyncio
import random

import discord

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
            self.logger.info("Not replying because %s", reason)
            return False

        self.logger.info("OK to reply")

        delay = await self._get_reply_delay()
        if delay > 0:
            await asyncio.sleep(delay)

        await self._process_reply()

    async def _process_reply(self):
        """Respond to this message immediately, if distance permits."""

        async with self.message.channel.typing():
            reply, distance = self._get_reply()

        acceptable_distance = self._get_distance_threshold()

        if distance <= acceptable_distance:
            self.logger.info("Sending reply")
            await self.message.channel.send(reply)
        else:
            self.logger.info(
                "Not replying because %.2f is greater than the threshold of %.2f",
                distance,
                acceptable_distance,
            )

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

    async def _get_reply_delay(self):
        """Return number of seconds to wait before replying to this message."""

        if self._is_direct():
            self.logger.info("Replying instantly to a direct message")
            return 0

        interval = await quantile_interval(
            self.client, self.message.channel, default=60
        )
        delay = interval * 1.5
        self.logger.info("Delaying by %.1f × 1.5 = %.1f seconds", interval, delay)
        return delay

    def _get_distance_threshold(self):
        """Return the maximum acceptible distance for replies to this message."""

        if self._is_direct():
            return 4
        else:
            return 1.5

    def _get_reply(self):
        """Return the chosen reply, and its distance, for this message."""

        self.logger.info("Preprocessing text")
        content = preprocess(self.client, self.message)

        self.logger.info("Selecting a reply")
        responses, distance = self.client.message_responder.get_all_responses(content)

        self.logger.info("%i replies produced", len(responses))
        filtered_responses = filter_responses(self.client, responses, self.message.channel)
        self.logger.info("%i replies after filtering", len(filtered_responses))

        if filtered_responses:
            reply = random.choice(filtered_responses).text
            self.logger.info('Selected reply "%s" at distance %.2f', reply, distance)
            return reply, distance

        self.logger.info("No suitable replies found")
        return None, distance
