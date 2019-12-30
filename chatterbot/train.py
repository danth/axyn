import logging
import os.path

import discord
from discord.ext import commands
from chatterbot.trainers import ListTrainer


# Set up logging
logger = logging.getLogger(__name__)


async def can_train(ctx):
    """Check if the user is allowed to train the bot."""

    # The bot owner can always train
    app_info = await ctx.bot.application_info()
    if ctx.author == app_info.owner:
        return True

    # Additional users can be specified in trainers.txt
    if not os.path.exists('trainers.txt'):
        return False

    # trainers.txt has one ID on each line
    with open('trainers.txt') as f:
        for line in f:
            # Check if this line has the user's ID
            if str(ctx.author.id) == line.strip():
                return True

    return False


class Training(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.check(can_train)
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
        await self.show_training(statements, ctx)

    async def show_training(self, statements, ctx):
        """Send a message showing the completed training."""

        # Build a string showing the conversation
        conversation = str()
        person_toggle = False
        for statement in statements:
            # Toggle between person A and person B
            person_toggle = not person_toggle
            if person_toggle: person = 'A'
            else:             person = 'B'
            # Add a line for this statement
            conversation += f'{person}: {statement}\n'

        # Send in embed as response to command
        e = discord.Embed(
            title='Training Completed',
            description=f'```\n{conversation}```',
        )
        e.set_author(
            name=ctx.author.name,
            icon_url=ctx.author.avatar_url
        )
        await ctx.send(embed=e)

        try:
            # Delete the command message
            await ctx.message.delete()
        except discord.Forbidden:
            # It doesn't matter if we can't
            pass


def setup(bot):
    bot.add_cog(Training(bot))
