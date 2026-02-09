from __future__ import annotations
from asyncio import create_task
from axyn.database import (
    ConsentResponse,
    MessageRecord,
    MessageRevisionRecord,
)
from axyn.managers.consent import ConsentManager
from axyn.managers.database import DatabaseManager
from axyn.managers.index import IndexManager
from axyn.managers.scan import ScanManager
from axyn.handlers.consent import ConsentHandler
from axyn.handlers.reply import ReplyHandler
from axyn.handlers.store import StoreHandler
from datetime import datetime
from discord import Client, Intents
from discord.app_commands import CommandTree
import logging
from sqlalchemy import update
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from asyncio import Task
    from discord import (
        ClientUser,
        Message,
        RawMessageUpdateEvent,
        RawMessageDeleteEvent,
        RawBulkMessageDeleteEvent,
        RawTypingEvent,
    )


class AxynClient(Client):
    def __init__(self):
        intents = Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(intents=intents)

        self.logger = logging.getLogger(__name__)

        # (author id, user id) → scheduled reply
        self.reply_tasks: dict[tuple[int, int], Task[None]] = dict()

        # user id → time last seen typing
        self.last_typing: dict[int, datetime] = dict()

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
        self.database_manager = DatabaseManager(self)
        await self.database_manager.setup_hook()

        self.consent_manager = ConsentManager(self)
        await self.consent_manager.setup_hook()

        self.index_manager = IndexManager(self)
        await self.index_manager.setup_hook()

        self.scan_manager = ScanManager(self)
        await self.scan_manager.setup_hook()

        self.logger.info("Syncing command definitions")
        create_task(self.command_tree.sync())

    async def on_ready(self):
        create_task(self.scan_manager.scan_all())

    async def on_message(self, message: Message):
        """Reply to and store incoming messages."""

        try:
            if self.last_typing[message.author.id] < message.created_at:
                del self.last_typing[message.author.id]
        except KeyError:
            pass

        # This must finish before the other tasks start, because they assume the
        # message is already in our database.
        await StoreHandler(self, message).handle()

        create_task(ConsentHandler(self, message).handle())
        create_task(ReplyHandler(self, message).handle())

    async def on_raw_message_edit(self, payload: RawMessageUpdateEvent):
        message = payload.message
        response = await self.consent_manager.get_response(message.author)

        if response == ConsentResponse.NO:
            self.logger.info(f"Not storing new revision of {message.id} because the author has not given consent")
            return

        self.logger.info(f"Storing new revision of {message.id}")

        async with self.database_manager.write_session() as session:
            await MessageRevisionRecord.insert(session, message)
            await session.commit()

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

    async def on_raw_typing(self, payload: RawTypingEvent):
        self.logger.debug(f"User {payload.user_id} is typing")

        self.last_typing[payload.user_id] = payload.timestamp

