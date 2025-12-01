from __future__ import annotations
from axyn.database import (
    ChannelRecord,
    ConsentResponse,
    GuildRecord,
    MessageRecord,
    MessageRevisionRecord,
    UserRecord,
)
from axyn.message_handlers import MessageHandler
from logging import getLogger
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from discord import Message


class Store(MessageHandler):
    def __init__(self, client: AxynClient, message: Message):
        super().__init__(client, message)

        self._logger = getLogger(__name__)

    async def handle(self):
        """Store this message."""

        if self.message.flags.ephemeral:
            self._logger.info(f"Not storing {self.message.id} because it is ephemeral")
            return

        response = await self.client.consent_manager.get_response(self.message.author)

        if response == ConsentResponse.NO:
            await self._store_redacted()
        else:
            await self._store_full()

    async def _store_full(self):
        """Store this message in full."""

        self._logger.info(f"Storing full version of {self.message.id}")

        async with self.client.database_manager.session() as session:
            if self.message.channel.guild is not None:
                await session.merge(GuildRecord.from_guild(self.message.channel.guild))
            await session.merge(ChannelRecord.from_channel(self.message.channel))
            await session.merge(UserRecord.from_user(self.message.author))

            session.add(MessageRecord.from_message(self.message))
            session.add(MessageRevisionRecord.from_message(self.message))

    async def _store_redacted(self):
        """
        Store a redacted version of this message.

        In other words, record the fact that a message existed at this point in
        time, but do not store any of its content.

        Dropping these messages entirely would create discontinuities in the
        history, potentially leading us to believe that messages are related
        when they are in fact separate. It would also increase the average
        delay between messages.
        """

        self._logger.info(f"Storing redacted version of {self.message.id}")

        async with self.client.database_manager.session() as session:
            if self.message.channel.guild is not None:
                await session.merge(GuildRecord.from_guild(self.message.channel.guild))
            await session.merge(ChannelRecord.from_channel(self.message.channel))
            await session.merge(UserRecord.from_user(self.message.author))

            session.add(MessageRecord.from_message(self.message))

