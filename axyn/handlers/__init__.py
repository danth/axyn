from __future__ import annotations
from abc import ABC, abstractmethod
from axyn.types import is_supported_channel_type
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from discord import Message


class Handler(ABC):
    def __init__(self, client: AxynClient, message: Message):
        """
        Create a new message handler for the given message.

        Raises an exception if the message is from a channel of an unsupported
        type.
        """

        if not is_supported_channel_type(message.channel):
            raise TypeError("unsupported channel type: {type(message.channel)}")

        self.client = client
        self.message = message
        self._channel = message.channel

    @abstractmethod
    async def handle(self):
        """Do whatever handling is required for this message."""

    def _attributes(self):
        """Return OpenTelemetry attributes for this message."""

        attributes = {
            "channel.id": self.message.channel.id,
            "message.id": self.message.id,
            "user.id": self.message.author.id,
        }

        if self.message.guild is not None:
            attributes["guild.id"] = self.message.guild.id

        return attributes
