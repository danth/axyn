from discord import (
    DMChannel,
    GroupChannel,
    Member,
    User,
)
from typing import Sequence, Union


def channel_members(channel) -> Sequence[Union[User, Member]]:
    """List everyone who can view a channel."""

    if isinstance(channel, DMChannel) or isinstance(channel, GroupChannel):
        return channel.recipients

    return channel.members

