from __future__ import annotations
from asyncio import create_task
from axyn.consent import ConsentManager
from axyn.database import (
    get_path,
    ConsentResponse,
    DatabaseManager,
    MessageRecord,
    MessageRevisionRecord,
)
from axyn.index import IndexManager
from axyn.message_handlers.consent import Consent
from axyn.message_handlers.reply import Reply
from axyn.message_handlers.store import Store
from datetime import datetime
from discord import Client, Intents
from discord.app_commands import CommandTree
import discordhealthcheck
import logging
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from asyncio import Task
    from discord import (
        ClientUser,
        Message,
        RawMessageUpdateEvent,
        RawMessageDeleteEvent,
        RawBulkMessageDeleteEvent,
    )


class AxynClient(Client):
    def __init__(self):
        intents = Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(intents=intents)

        self.logger = logging.getLogger(__name__)

        self.reply_tasks: dict[int, Task[None]] = dict()

        self.command_tree = CommandTree(self)

    def axyn(self) -> ClientUser:
        """
        Return Axyn's Discord user.

        Raises an error if the client is not logged in yet.
        """

        if self.user is None:
            raise Exception("Client must be logged in to access the Axyn user")

        return self.user

    async def setup_hook(self):
        self.database_manager = DatabaseManager()
        await self.database_manager.setup_hook()

        self.consent_manager = ConsentManager(self, self.database_manager)
        await self.consent_manager.setup_hook()

        self.index_manager = IndexManager(self, get_path("index"))
        await self.index_manager.setup_hook()

        self.logger.info("Syncing command definitions")
        create_task(self.command_tree.sync())

        self.logger.info("Starting Docker health check")
        await discordhealthcheck.start(self)

    async def on_message(self, message: Message):
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

        # This must finish before the other tasks start, because they assume the
        # message is already in our database.
        await Store(self, message).handle()

        create_task(Consent(self, message).handle())

        reply = create_task(Reply(self, message).handle())
        self.reply_tasks[message.channel.id] = reply

    async def on_raw_message_edit(self, payload: RawMessageUpdateEvent):
        message = payload.message
        response = await self.consent_manager.get_response(message.author)

        if response == ConsentResponse.NO:
            self.logger.info(f"Not storing new revision of {message.id} because the author has not given consent")
            return

        try:
            async with self.database_manager.write_session() as session:
                session.add(MessageRevisionRecord.from_message(message))

                await session.commit()
        except IntegrityError:
            # The unique constraint fails when Discord resolves a link into an
            # embed, for example, because that counts as an update but doesn't
            # affect the content.
            # The foreign key constraint fails if we didn't see the original
            # version of the message.
            self.logger.info(f"New revision of {message.id} rejected by database constraints")
        else:
            self.logger.info(f"Storing new revision of {message.id}")

    async def on_raw_message_delete(self, payload: RawMessageDeleteEvent):
        self.logger.info(f"Marking {payload.message_id} as deleted")

        async with self.database_manager.write_session() as session:
            await session.execute(
                update(MessageRecord)
                .where(MessageRecord.message_id == payload.message_id)
                .values(deleted_at=datetime.now())
            )

            await session.commit()

    async def on_raw_bulk_message_delete(self, payload: RawBulkMessageDeleteEvent):
        self.logger.info(f"Marking {payload.message_ids} as deleted")

        async with self.database_manager.write_session() as session:
            await session.execute(
                update(MessageRecord)
                .where(MessageRecord.message_id.in_(payload.message_ids))
                .values(deleted_at=datetime.now())
            )

            await session.commit()

