from axyn.message_handlers import MessageHandler
from axyn.filters import reason_not_to_react
from axyn.preprocessor import preprocess


class React(MessageHandler):
    async def handle(self):
        """React to this message, if possible."""

        reason = reason_not_to_react(self.bot, self.message)
        if reason:
            self.logger.info("Not reacting because %s", reason)
            return

        self.logger.info("Preprocessing text")
        content = preprocess(self.bot, self.message)

        self.logger.info("Getting reaction")
        emoji, distance = self.bot.reaction_responder.get_response(content)

        if distance <= 2:
            self.logger.info("Reacting with %s", emoji)
            await self.message.add_reaction(emoji)
        else:
            self.logger.info("Not reacting because %.2f is greater than the threshold of 2", distance)
