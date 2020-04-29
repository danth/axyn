import logging

import discord
from discord.ext import commands

from axyn.chatbot.train import train_statement
from axyn.models import Trainer

# Set up logging
logger = logging.getLogger(__name__)


async def can_train(ctx):
    """Check if the user is allowed to train the bot."""

    session = ctx.bot.Session()
    trainer = session.query(Trainer).filter(Trainer.id == ctx.author.id).one_or_none()
    session.close()

    return trainer is not None


class Training(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.check(can_train)
    async def train(self, ctx, *, training):
        """
        Train the bot with an example conversation.

        This is a way to manually input small sections of training data,
        normally just made up by yourself on the spot. Large trainings, such as
        from a corpus, should be made by other means.

        There is no guarantee that responses trained using this command will be
        selected, since other responses to the same input text may also have
        been learned.

        Place one statement on each line, including the first, such that the
        first sentence is directly after `a!train`, and other sentences are on
        the following lines. Multi-line statements are *not* supported.
        """

        logger.info("Processing training from command")

        async with ctx.channel.typing():
            # Split statements on newline
            statements = training.split("\n")

            # Do training
            session = self.bot.Session()

            previous_statement = None
            for statement in statements:
                # The first statement is not saved as it has nothing it is
                # responding to
                if previous_statement is not None:
                    # Create a statement in response to the previous one
                    train_statement(statement, previous_statement, session)
                previous_statement = statement

            session.close()

        # Completed, respond to command
        logger.info("Sending response")
        await self.show_training(statements, ctx, ctx.channel)

        appinfo = await ctx.bot.application_info()
        if ctx.author != appinfo.owner:
            # Also send a copy to bot owner
            logger.info("Sending to bot owner")
            await self.show_training(statements, ctx, appinfo.owner)

        try:
            # Delete the command message
            logger.info("Attempting to delete command")
            await ctx.message.delete()
        except discord.Forbidden:
            # It doesn't matter if we can't
            pass

        logger.info("Done!")

    async def show_training(self, statements, ctx, send_to):
        """Send a message showing the completed training."""

        # Build a string showing the conversation
        conversation = str()
        person_toggle = False
        for statement in statements:
            # Toggle between person A and person B
            person_toggle = not person_toggle
            if person_toggle:
                person = "A"
            else:
                person = "B"
            # Add a line for this statement
            conversation += f"{person}: {statement}\n"

        # Send in embed as response to command
        e = discord.Embed(
            title="Training Completed", description=f"```\n{conversation}```",
        )
        e.set_footer(text=ctx.author.name, icon_url=ctx.author.avatar_url)
        await send_to.send(embed=e)

    @commands.group()
    @commands.is_owner()
    async def trainers(self, ctx):
        """
        Manage users who are allowed to use `a!train`.

        As the bot owner, it is necessary to add yourself as a trainer before
        you can use the training command. Only the owner of the bot can manage
        training permissions.

        Call with no sub-command to list all users who currently have the
        permission.
        """

        if ctx.subcommand_passed is not None:
            # A subcommand was called / attempted to be called
            return

        session = self.bot.Session()
        trainers = session.query(Trainer).all()

        if len(trainers) == 0:
            # There are no trainers
            await ctx.send(
                embed=discord.Embed(
                    title="Trainers",
                    description="Nobody has permission to train Axyn manually.",
                )
            )
        else:
            # Build a list of either a mention or ID for each trainer
            trainer_list = list()
            for trainer in trainers:
                user = self.bot.get_user(trainer.id)
                if user is not None:
                    # Mention the user
                    trainer_list.append(user.mention)
                else:
                    # We couldn't find the user, show ID instead
                    trainer_list.append(trainer.id)

            # Send to channel
            await ctx.send(
                embed=discord.Embed(
                    title="Trainers", description="\n".join(trainer_list)
                )
            )

        session.close()

    @trainers.command(aliases=["a"])
    async def add(self, ctx, user: discord.User):
        """
        Give a user permission to use `a!train`.

        If you are unable to easily mention the user (if you are using this
        command in a DM, for example), you may pass a user ID instead.
        """

        session = self.bot.Session()
        trainer = session.query(Trainer).filter(Trainer.id == user.id).one_or_none()

        if trainer is not None:
            # The user already has permission
            await ctx.send(
                embed=discord.Embed(
                    description=f"{user.mention} is already a trainer.",
                    color=discord.Color.orange(),
                )
            )
        else:
            # Add the user to the trainers list
            session.add(Trainer(id=user.id))
            session.commit()

            await ctx.send(
                embed=discord.Embed(
                    description=f"{user.mention} has been added as a trainer!",
                    color=discord.Color.green(),
                )
            )

        session.close()

    @trainers.command(aliases=["r"])
    async def remove(self, ctx, user: discord.User):
        """
        Remove a user's permission to use `a!train`.

        If the user did not have permission anyway, this command will have no
        effect.

        If you are unable to easily mention the user (if you are using this
        command in a DM, for example), you may pass a user ID instead.
        """

        session = self.bot.Session()
        session.query(Trainer).filter(Trainer.id == user.id).delete()
        session.commit()
        session.close()

        await ctx.send(
            embed=discord.Embed(
                description=f"{user.mention} has been removed as a trainer.",
                color=discord.Color.green(),
            )
        )


def setup(bot):
    bot.add_cog(Training(bot))
