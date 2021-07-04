from flipgenic import Message

from axyn.filters import reason_not_to_learn_reaction_pair
from axyn.preprocessor import preprocess
from axyn.reaction_handlers import ReactionHandler


class LearnReaction(ReactionHandler):
    async def handle(self):
        reason = reason_not_to_learn_reaction_pair(
            self.client, self.reaction, self.reaction_user
        )
        if reason:
            self.logger.info("Not learning because %s", reason)
            return

        self.logger.info("Preprocessing text")
        content = preprocess(self.client, self.reaction.message)

        self.logger.info(
            'Learning %s as a reaction to "%s"', self.reaction.emoji, content
        )
        self.client.reaction_responder.learn_response(
            content,
            Message(
                self.reaction.emoji,
                self.reaction.message.channel.id,
            ),
        )
        self.logger.info("Learning complete")
