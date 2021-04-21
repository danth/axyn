from axyn.reaction_handlers import ReactionHandler
from axyn.preprocessor import preprocess
from axyn.filters import reason_not_to_learn_reaction_pair


class LearnReaction(ReactionHandler):
    async def handle(self):
        reason = reason_not_to_learn_reaction_pair(
            self.bot, self.reaction, self.reaction_user
        )
        if reason:
            self.logger.info("Not learning because %s", reason)
            return

        self.logger.info("Preprocessing text")
        content = preprocess(self.bot, self.reaction.message)

        self.logger.info('Learning %s as a reaction to "%s"', self.reaction.emoji, content)
        self.bot.reaction_responder.learn_response(content, self.reaction.emoji)
        self.logger.info("Learning complete")
