import asyncio
import logging
from discord.ext import commands

from axyn.message_handlers.react import React
from axyn.message_handlers.reply import Reply
from axyn.message_handlers.learn import Learn
from axyn.reaction_handlers.learn import LearnReaction

# Set up logging
logger = logging.getLogger(__name__)


class Handle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reply_tasks = dict()

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle the message with all handlers."""

        # If the reply handler decides to delay, this will cancel previous
        # tasks in the channel so only the last message in a conversation
        # finishes the timer and recieves a reply.
        if message.channel.id in self.reply_tasks:
            logger.info("Cancelling reply task in channel %i due to a newer message", message.channel.id)
            self.reply_tasks[message.channel.id].cancel()

        logger.info("Queueing reply task for %i", message.id)
        self.reply_tasks[message.channel.id] = asyncio.create_task(
            Reply(self.bot, message).handle()
        )

        logger.info("Queueing react task for %i", message.id)
        asyncio.create_task(React(self.bot, message).handle())

        logger.info("Queueing learn task for %i", message.id)
        asyncio.create_task(Learn(self.bot, message).handle())

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, reaction_user):
        """Handle the reaction with all handlers."""

        logger.info("Queueing learn task for reaction to %i", reaction.message.id)
        asyncio.create_task(LearnReaction(self.bot, reaction, reaction_user).handle())


def setup(bot):
    bot.add_cog(Handle(bot))
