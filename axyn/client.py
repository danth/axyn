import asyncio
from datetime import datetime
import logging

import discord
from discord import (
    RawMessageUpdateEvent,
    RawMessageDeleteEvent,
    RawBulkMessageDeleteEvent,
)
import discordhealthcheck
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from axyn.consent import ConsentManager
from axyn.database import (
    get_path,
    DatabaseManager,
    MessageRecord,
    MessageRevisionRecord,
)
from axyn.index import IndexManager
from axyn.message_handlers.consent import Consent
from axyn.message_handlers.reply import Reply
from axyn.message_handlers.store import Store


class AxynClient(discord.Client):
    def __init__(self, *args, **kwargs):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(*args, intents=intents, **kwargs)

        self.logger = logging.getLogger(__name__)

        self.reply_tasks = dict()

        self.command_tree = discord.app_commands.CommandTree(self)

    async def setup_hook(self):
        self.database_manager = DatabaseManager()
        await self.database_manager.setup_hook()

        self.consent_manager = ConsentManager(self, self.database_manager)
        await self.consent_manager.setup_hook()

        self.index_manager = IndexManager(self, get_path("index"))
        await self.index_manager.setup_hook()

        self.logger.info("Syncing command definitions")
        asyncio.create_task(self.command_tree.sync())

        self.logger.info("Starting Docker health check")
        asyncio.create_task(discordhealthcheck.start(self))

    async def on_message(self, message):
        """Reply to and store incoming messages."""

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
        asyncio.create_task(Store(self, message).handle())
        asyncio.create_task(Consent(self, message).handle())

    async def on_raw_message_edit(self, payload: RawMessageUpdateEvent):
        message = payload.message

        if not self.consent_manager.has_consented(message.author):
            self.logger.info(f"Not storing new revision of {message.id} because the author has not given consent")
            return

        try:
            async with self.database_manager.session() as session:
                    await session.merge(MessageRevisionRecord.from_message(message))
        except IntegrityError:
            # Happens when Discord resolves a link into an embed, for example,
            # because that also counts as an update.
            self.logger.info(f"Not storing new revision of {message.id} because the content has not changed")
        else:
            self.logger.info(f"Storing new revision of {message.id}")

    async def on_raw_message_delete(self, payload: RawMessageDeleteEvent):
        self.logger.info(f"Marking {payload.message_id} as deleted")

        async with self.database_manager.session() as session:
            await session.execute(
                update(MessageRecord)
                .where(MessageRecord.message_id == payload.message_id)
                .values(deleted_at=datetime.now())
            )

    async def on_raw_bulk_message_delete(self, payload: RawBulkMessageDeleteEvent):
        self.logger.info(f"Marking {payload.message_ids} as deleted")

        async with self.database_manager.session() as session:
            await session.execute(
                update(MessageRecord)
                .where(MessageRecord.message_id.in_(payload.message_ids))
                .values(deleted_at=datetime.now())
            )

