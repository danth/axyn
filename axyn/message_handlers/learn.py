import logging
from datetime import timedelta

from flipgenic import Message
from logdecorator import log_on_end, log_on_start
from logdecorator.asyncio import async_log_on_end, async_log_on_start

from axyn.filters import reason_not_to_learn, reason_not_to_learn_pair
from axyn.interval import quantile_interval
from axyn.message_handlers import MessageHandler
from axyn.preprocessor import preprocess


@log_on_start(
    logging.INFO,
    'Learning "{message.clean_content}" as a reply to "{previous.clean_content}"',
)
@log_on_end(logging.DEBUG, "Learning complete")
def _learn(client, previous, message):
    """Learn a response pair after preprocessing."""

    previous_content = preprocess(client, previous)
    content = preprocess(client, message)

    client.message_responder.learn_response(
        previous_content,
        Message(content, message.channel.id),
    )


class Learn(MessageHandler):
    async def handle(self):
        """Learn this message, if allowed."""

        reason = reason_not_to_learn(self.client, self.message)
        if reason:
            return

        previous = await self.get_previous()
        if not previous:
            return

        reason = reason_not_to_learn_pair(self.client, previous, self.message)
        if reason:
            return

        _learn(self.client, previous, self.message)

    @async_log_on_start(logging.DEBUG, "Searching for a previous message")
    async def get_previous(self):
        """Return the message this message was seemingly in response to, if any."""

        reference = self._get_reference()
        if reference:
            return reference

        recent = await self._get_recent()
        if recent:
            return recent

    @log_on_end(logging.DEBUG, "This message references {result}")
    def _get_reference(self):
        """Return the message this message references, if any."""

        if self.message.reference and self.message.reference.resolved:
            return self.message.reference.resolved

    @async_log_on_end(logging.DEBUG, "{result} was sent recently")
    async def _get_recent(self):
        """Return the message just before this message, if it was recent."""

        threshold = await quantile_interval(
            self.client,
            self.message.channel,
            quantile=0.75,
            default=300,
        )

        history = await self.message.channel.history(
            # Find messages before self
            before=self.message,
            # Only request a single message
            limit=1,
            oldest_first=False,
            # Limit to messages within threshold
            after=self.message.created_at - timedelta(seconds=threshold),
        ).flatten()

        if len(history) > 0:
            return history[0]
