from __future__ import annotations
from asyncio import Queue, TaskGroup, create_task
from axyn.handlers.store import StoreHandler
from axyn.managers import Manager
from axyn.types import is_supported_channel_type
from discord.errors import Forbidden
from opentelemetry.trace import get_tracer
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from axyn.types import ChannelUnion
    from discord import Message


_tracer = get_tracer(__name__)


class ScanManager(Manager):
    _queue: Queue[Message]

    def __init__(self, client: AxynClient):
        super().__init__(client)

        self._queue = Queue(1024)

    @_tracer.start_as_current_span("set up scan manager")
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

        with _tracer.start_as_current_span(
            "scan channel",
            attributes={"channel.id": channel.id},
        ) as span:
            try:
                async for message in channel.history(limit=None):
                    await self._queue.put(message)
            except Forbidden:
                span.add_event(f"Cancelled due to insufficient permissions")

    @_tracer.start_as_current_span("scan everything")
    async def scan_all(self):
        """Scan the history of all visible channels for unseen messages."""

        async with TaskGroup() as group:
            for channel in self._client.get_all_channels():
                if is_supported_channel_type(channel):
                    group.create_task(self.scan_channel(channel))
