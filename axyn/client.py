import asyncio
import logging

import discord
import discordhealthcheck
import spacy
from discord_slash import SlashCommand
from flipgenic import Responder

from axyn.consent import ConsentManager
from axyn.datastore import get_path
from axyn.message_handlers.learn import Learn
from axyn.message_handlers.react import React
from axyn.message_handlers.reply import Reply
from axyn.reaction_handlers.learn import LearnReaction


class AxynClient(discord.Client):
    def __init__(self, *args, **kwargs):
        intents = discord.Intents.default()
        intents.members = True  # Required for on_reaction_add in DMs
        super().__init__(*args, intents=intents, **kwargs)

        self.logger = logging.getLogger(__name__)

        self.reply_tasks = dict()

        self.slash = SlashCommand(self, sync_commands=True)
        self.consent_manager = ConsentManager(self)

        self.logger.info("Loading SpaCy model")
        # Loading the model here stops Flipgenic creating two separate instances
        self.spacy_model = spacy.load("en_core_web_md", exclude=["ner"])
        self.logger.info("Loading message responder")
        self.message_responder = Responder(get_path("messages"), self.spacy_model)
        self.logger.info("Loading reaction responder")
        self.reaction_responder = Responder(get_path("reactions"), self.spacy_model)

        self.logger.info("Starting Docker health check")
        discordhealthcheck.start(self)

    async def on_message(self, message):
        """Reply to, react to, and learn incoming messages."""

        # If the reply handler decides to delay, this will cancel previous
        # tasks in the channel so only the last message in a conversation
        # finishes the timer and recieves a reply.
        if message.channel.id in self.reply_tasks:
            self.logger.info(
                "Cancelling reply task in channel %i due to a newer message",
                message.channel.id,
            )
            self.reply_tasks[message.channel.id].cancel()

        self.reply_tasks[message.channel.id] = asyncio.create_task(
            Reply(self, message).handle()
        )
        asyncio.create_task(React(self, message).handle())
        asyncio.create_task(Learn(self, message).handle())

    async def on_reaction_add(self, reaction, reaction_user):
        """Learn incoming reactions."""

        asyncio.create_task(LearnReaction(self, reaction, reaction_user).handle())

    async def on_component(self, ctx):
        """Handle consent interactions."""

        await self.consent_manager.handle_button(ctx)
