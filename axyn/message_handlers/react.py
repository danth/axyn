import random

from axyn.filters import reason_not_to_react
from axyn.message_handlers import MessageHandler
from axyn.preprocessor import preprocess
from axyn.privacy import filter_responses


class React(MessageHandler):
    async def handle(self):
        """React to this message, if possible."""

        reason = reason_not_to_react(self.client, self.message)
        if reason:
            self.logger.info("Not reacting because %s", reason)
            return

        self.logger.info("Preprocessing text")
        content = preprocess(self.client, self.message)

        self.logger.info("Getting reaction")
        responses, distance = self.client.reaction_responder.get_all_responses(content)

        self.logger.info("%i reactions produced", len(responses))
        filtered_responses = filter_responses(
            self.client, responses, self.message.channel
        )
        self.logger.info("%i reactions after filtering", len(filtered_responses))

        if distance <= 2:
            emoji = random.choice(filtered_responses).text
            self.logger.info("Reacting with %s", emoji)
            await self.message.add_reaction(emoji)
        else:
            self.logger.info(
                "Not reacting because %.2f is greater than the threshold of 2", distance
            )
