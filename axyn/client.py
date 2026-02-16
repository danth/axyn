from __future__ import annotations
from asyncio import TaskGroup
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
from axyn.handlers.respond import RespondHandler
from axyn.handlers.store import StoreHandler
from datetime import datetime
from discord import Client, Intents
from discord.app_commands import CommandTree
from opentelemetry.trace import get_current_span, get_tracer
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


_tracer = get_tracer(__name__)


class AxynClient(Client):
    def __init__(self):
        intents = Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(intents=intents)

        # (author id, user id) → scheduled response
        self.response_tasks: dict[tuple[int, int], Task[None]] = dict()

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

    @_tracer.start_as_current_span("set up client")
    async def setup_hook(self):
        self.database_manager = DatabaseManager(self)
        await self.database_manager.setup_hook()

        self.consent_manager = ConsentManager(self)
        await self.consent_manager.setup_hook()

        self.index_manager = IndexManager(self)
        await self.index_manager.setup_hook()

        self.scan_manager = ScanManager(self)
        await self.scan_manager.setup_hook()

        await self.command_tree.sync()

    @_tracer.start_as_current_span("handle client reaching ready state")
    async def on_ready(self):
        await self.scan_manager.scan_all()

    async def on_message(self, message: Message):
        attributes = {
            "channel.id": message.channel.id,
            "message.id": message.id,
        }

        if message.guild is not None:
            attributes["guild.id"] = message.guild.id

        with _tracer.start_as_current_span(
            "handle new message",
            attributes=attributes,
        ):
            await self._on_message(message)

    async def _on_message(self, message: Message):
        try:
            if self.last_typing[message.author.id] < message.created_at:
                del self.last_typing[message.author.id]
        except KeyError:
            pass

        # This must finish before the other tasks start, because they assume the
        # message is already in our database.
        await StoreHandler(self, message).handle()

        async with TaskGroup() as group:
            group.create_task(ConsentHandler(self, message).handle())
            group.create_task(RespondHandler(self, message).handle())

    async def on_raw_message_edit(self, payload: RawMessageUpdateEvent):
        attributes = {
            "channel.id": payload.channel_id,
            "message.id": payload.message_id,
        }

        if payload.guild_id is not None:
            attributes["guild.id"] = payload.guild_id

        with _tracer.start_as_current_span(
            "handle edited message",
            attributes=attributes,
        ):
            await self._on_raw_message_edit(payload)

    async def _on_raw_message_edit(self, payload: RawMessageUpdateEvent):
        message = payload.message

        async with self.database_manager.session() as session:
            response = await self.consent_manager.get_response(session, message.author)

            if response == ConsentResponse.NO:
                get_current_span().add_event("Not storing because the author has not given consent")
                return

            await MessageRevisionRecord.insert(session, message)
            await session.commit()

    async def on_raw_message_delete(self, payload: RawMessageDeleteEvent):
        attributes = {
            "channel.id": payload.channel_id,
            "message.id": payload.message_id,
        }

        if payload.guild_id is not None:
            attributes["guild.id"] = payload.guild_id

        with _tracer.start_as_current_span(
            "handle deleted message",
            attributes=attributes,
        ):
            await self._on_raw_message_delete(payload)

    async def _on_raw_message_delete(self, payload: RawMessageDeleteEvent):
        async with self.database_manager.session() as session:
            await session.execute(
                update(MessageRecord)
                .where(MessageRecord.message_id == payload.message_id)
                .values(deleted_at=datetime.now())
            )

            await session.commit()

    async def on_raw_bulk_message_delete(self, payload: RawBulkMessageDeleteEvent):
        attributes = {"channel.id": payload.channel_id}

        if payload.guild_id is not None:
            attributes["guild.id"] = payload.guild_id

        with _tracer.start_as_current_span(
            "handle bulk-deleted messages",
            attributes=attributes,
        ):
            await self._on_raw_bulk_message_delete(payload)

    async def _on_raw_bulk_message_delete(self, payload: RawBulkMessageDeleteEvent):
        async with self.database_manager.session() as session:
            await session.execute(
                update(MessageRecord)
                .where(MessageRecord.message_id.in_(payload.message_ids))
                .values(deleted_at=datetime.now())
            )

            await session.commit()

    async def on_raw_typing(self, payload: RawTypingEvent):
        attributes = {
            "channel.id": payload.channel_id,
            "user.id": payload.user_id,
        }

        if payload.guild_id is not None:
            attributes["guild.id"] = payload.guild_id

        with _tracer.start_as_current_span(
            "handle typing notification",
            attributes=attributes,
        ):
            await self._on_raw_typing(payload)

    async def _on_raw_typing(self, payload: RawTypingEvent):
            self.last_typing[payload.user_id] = payload.timestamp

