from datetime import timedelta

from axyn.filters import reason_not_to_learn, reason_not_to_learn_pair
from axyn.message_handlers import MessageHandler
from axyn.preprocessor import preprocess


class Learn(MessageHandler):
    async def handle(self):
        """Learn this message, if allowed."""

        reason = reason_not_to_learn(self.bot, self.message)
        if reason:
            self.logger.info("Not learning because %s", reason)
            return

        previous = await self.get_previous()
        if not previous:
            return

        reason = reason_not_to_learn_pair(self.bot, previous, self.message)
        if reason:
            self.logger.info("Not learning because %s", reason)
            return

        self.logger.info("Preprocessing texts")
        previous_content = preprocess(self.bot, previous)
        content = preprocess(self.bot, self.message)

        self.logger.info('Learning "%s" as a reply to "%s"', content, previous_content)
        self.bot.message_responder.learn_response(previous_content, content)
        self.logger.info("Learning complete")

    async def get_previous(self):
        """Return the message this message was seemingly in response to, if any."""

        self.logger.info("Searching for a previous message")

        reference = self._get_reference()
        if reference:
            self.logger.info(
                '"%s" is replied to by this message',
                reference.clean_content,
            )
            return reference

        recent = await self._get_recent()
        if recent:
            self.logger.info(
                '"%s" was recently sent in the same channel as this message',
                recent.clean_content,
            )
            return recent

        self.logger.info("No previous message found")

    def _get_reference(self):
        """Return the message this message references, if any."""

        if self.message.reference and self.message.reference.resolved:
            return self.message.reference.resolved

    async def _get_recent(self, minutes=5):
        """Return the message just before this message, if it was recent."""

        history = await self.message.channel.history(
            # Find messages before self
            before=self.message,
            # Only request a single message
            limit=1,
            oldest_first=False,
            # Limit to messages within timeframe
            after=self.message.created_at - timedelta(minutes=minutes),
        ).flatten()

        if len(history) > 0:
            return history[0]
