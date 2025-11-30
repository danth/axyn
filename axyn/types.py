from __future__ import annotations
from discord import (
    DMChannel,
    GroupChannel,
    TextChannel,
    VoiceChannel,
)
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from discord import User, Member
    from typing import Any, Union, TypeIs

    ChannelUnion = Union[
        DMChannel,
        GroupChannel,
        TextChannel,
        VoiceChannel,
    ]

    UserUnion = Union[
        User,
        Member,
    ]


def is_supported_channel_type(channel: Any) -> TypeIs[ChannelUnion]:
    """Return whether the given channel is of a type we support."""

    return (
        isinstance(channel, DMChannel) or
        isinstance(channel, GroupChannel) or
        isinstance(channel, TextChannel) or
        isinstance(channel, VoiceChannel)
    )

