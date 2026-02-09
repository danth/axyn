from __future__ import annotations
from asyncio import Queue, TaskGroup, create_task
from axyn.handlers.store import StoreHandler
from axyn.managers import Manager
from axyn.types import is_supported_channel_type
from discord.errors import Forbidden
from logging import getLogger
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from axyn.types import ChannelUnion
    from discord import Message
    from logging import Logger


class ScanManager(Manager):
    _logger: Logger
    _queue: Queue[Message]

    def __init__(self, client: AxynClient):
        super().__init__(client)

        self._logger = getLogger(__name__)
        self._queue = Queue(1024)

    async def setup_hook(self):
        create_task(self._handle())

    async def _handle(self):
        """
        Background task which stores messages coming from a priority queue.

        There is no benefit to processing messages in parallel, because
        most of the processing involves SQLite which has a global lock.
        """

        while True:
            message = await self._queue.get()
            await StoreHandler(self._client, message).handle()

    async def scan_channel(self, channel: ChannelUnion):
        """Scan the history of the given channel for unseen messages."""

        self._logger.info(f"Started scan of channel {channel.id}")

        try:
            async for message in channel.history(limit=None):
                await self._queue.put(message)
        except Forbidden:
            self._logger.info(f"Cancelled scan of channel {channel.id} due to insufficient permissions")
        else:
            self._logger.info(f"Queued all messages from channel {channel.id}")

    async def scan_all(self):
        """Scan the history of all visible channels for unseen messages."""

        async with TaskGroup() as group:
            for channel in self._client.get_all_channels():
                if is_supported_channel_type(channel):
                    group.create_task(self.scan_channel(channel))
