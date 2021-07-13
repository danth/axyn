import logging
import random

from axyn.filters import reason_not_to_react
from axyn.message_handlers import MessageHandler
from axyn.preprocessor import preprocess
from axyn.privacy import filter_responses
from logdecorator import log_on_start, log_on_end
from logdecorator.asyncio import async_log_on_start


class React(MessageHandler):
    async def handle(self):
        """React to this message, if possible."""

        reason = reason_not_to_react(self.client, self.message)
        if reason:
            return

        emoji, distance = self._get_reaction()
        acceptable_distance = self._get_distance_threshold()

        if distance <= acceptable_distance:
            await self._add_reaction(emoji)

    @log_on_end(logging.INFO, "The distance threshold is {result}")
    def _get_distance_threshold(self):
        """Return the maximum acceptible distance for reactions to this message."""

        return 2

    @log_on_start(logging.DEBUG, 'Getting reaction to "{self.message.clean_content}"')
    @log_on_end(logging.INFO, 'Selected reaction {result[0]} at distance {result[1]}')
    def _get_reaction(self):
        """Return the chosen reaction, and its distance, for this message."""

        content = preprocess(self.client, self.message)
        responses, distance = self.client.reaction_responder.get_all_responses(content)

        filtered_responses = filter_responses(
            self.client, responses, self.message.channel
        )

        if filtered_responses:
            emoji = random.choice(filtered_responses).text
            return emoji, distance

        return None, float("inf")

    @async_log_on_start(logging.INFO, 'Adding reaction {emoji}')
    async def _add_reaction(self, emoji):
        """Add a reaction."""

        await self.message.add_reaction(emoji)
