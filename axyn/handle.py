import asyncio
import logging

from axyn.message_handlers.learn import Learn
from axyn.message_handlers.react import React
from axyn.message_handlers.reply import Reply
from axyn.reaction_handlers.learn import LearnReaction

# Set up logging
logger = logging.getLogger(__name__)


def setup_handlers(client):
    reply_tasks = dict()

    @client.event
    async def on_message(message):
        """Handle the message with all handlers."""

        # If the reply handler decides to delay, this will cancel previous
        # tasks in the channel so only the last message in a conversation
        # finishes the timer and recieves a reply.
        if message.channel.id in reply_tasks:
            logger.info(
                "Cancelling reply task in channel %i due to a newer message",
                message.channel.id,
            )
            reply_tasks[message.channel.id].cancel()

        logger.info("Queueing reply task for %i", message.id)
        reply_tasks[message.channel.id] = asyncio.create_task(
            Reply(client, message).handle()
        )

        logger.info("Queueing react task for %i", message.id)
        asyncio.create_task(React(client, message).handle())

        logger.info("Queueing learn task for %i", message.id)
        asyncio.create_task(Learn(client, message).handle())

    @client.event
    async def on_reaction_add(reaction, reaction_user):
        """Handle the reaction with all handlers."""

        logger.info("Queueing learn task for reaction to %i", reaction.message.id)
        asyncio.create_task(LearnReaction(client, reaction, reaction_user).handle())
