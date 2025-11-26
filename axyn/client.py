import asyncio
import logging

import discord
import discordhealthcheck
import spacy

from axyn.chatbot import Responder
from axyn.consent import ConsentManager
from axyn.database import get_path, DatabaseManager
from axyn.message_handlers.learn import Learn
from axyn.message_handlers.reply import Reply


class AxynClient(discord.Client):
    def __init__(self, *args, **kwargs):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(*args, intents=intents, **kwargs)

        self.logger = logging.getLogger(__name__)

        self.reply_tasks = dict()

        self.command_tree = discord.app_commands.CommandTree(self)

        self.database_manager = DatabaseManager()
        self.consent_manager = ConsentManager(self, self.database_manager)

        self.logger.info("Loading SpaCy model")
        self.spacy_model = spacy.load("en_core_web_md", exclude=["ner"])
        self.logger.info("Loading message responder")
        self.message_responder = Responder(get_path("index"), self, self.spacy_model)

    async def setup_hook(self):
        self.consent_manager.setup_hook()

        self.logger.info("Syncing command definitions")
        asyncio.create_task(self.command_tree.sync())

        self.logger.info("Starting Docker health check")
        asyncio.create_task(discordhealthcheck.start(self))

    async def on_message(self, message):
        """Reply to and learn incoming messages."""

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
        asyncio.create_task(Learn(self, message).handle())

