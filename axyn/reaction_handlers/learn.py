import logging

from flipgenic import Message
from logdecorator import log_on_end, log_on_start

from axyn.filters import reason_not_to_learn_reaction_pair
from axyn.preprocessor import preprocess
from axyn.reaction_handlers import ReactionHandler


@log_on_start(
    logging.INFO, 'Learning {emoji} as a reaction to "{message.clean_content}"'
)
@log_on_end(logging.DEBUG, "Learning complete")
def _learn(client, message, emoji):
    """Learn a reaction after preprocessing."""

    content = preprocess(client, message)

    client.reaction_responder.learn_response(
        content,
        Message(emoji, message.channel.id),
    )


class LearnReaction(ReactionHandler):
    async def handle(self):
        reason = reason_not_to_learn_reaction_pair(
            self.client, self.reaction, self.reaction_user
        )
        if reason:
            return

        _learn(self.client, self.reaction.message, self.reaction.emoji)
