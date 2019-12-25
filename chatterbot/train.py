import logging

from discord.ext import commands
from chatterbot.trainers import ListTrainer


# Set up logging
logger = logging.getLogger(__name__)


class Training(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def train(self, ctx, *, training):
        """
        Train the bot with an example conversation.

        Place one statement on each line, including the first.
        """

        logger.info('Processing list training from command')

        async with ctx.channel.typing():
            # Split statements on newline
            statements = training.split('\n')

            # Do training
            trainer = ListTrainer(self.bot.chatter)
            trainer.train(statements)

        # Completed, respond to command
        logger.info('Done!')
        await ctx.send('Done!')


def setup(bot):
    bot.add_cog(Training(bot))
