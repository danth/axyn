from __future__ import annotations
from discord import DMChannel, GroupChannel
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.types import ChannelUnion, UserUnion
    from typing import Sequence


def channel_members(channel: ChannelUnion) -> Sequence[UserUnion]:
    """List everyone who can view a channel."""

    if isinstance(channel, DMChannel) or isinstance(channel, GroupChannel):
        return channel.recipients

    return channel.members

