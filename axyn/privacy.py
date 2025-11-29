from discord import (
    DMChannel,
    GroupChannel,
    Member,
    User,
)
from typing import Sequence, Union

from axyn.database import MessageRevisionRecord


def _members_to_set(users: Sequence[Union[User, Member]]) -> set[int]:
    """
    Convert a list of members to a set of their IDs.

    Bot users are filtered out.
    """

    return set(user.id for user in users if not (user.bot or user.system))


def _channel_members(channel) -> Sequence[Union[User, Member]]:
    """List everyone who can view a channel."""

    if isinstance(channel, DMChannel) or isinstance(channel, GroupChannel):
        return channel.recipients

    return channel.members


def can_send_in_channel(client, message: MessageRevisionRecord, current_channel):
    """
    Return whether a message may be sent to a channel.

    This is only true if everyone who can view the current channel can also
    view the channel where the message was originally sent.
    """

    original_channel = client.get_channel(message.message.channel_id)

    if original_channel is None:
        # We are unable to fetch the member list for the original channel
        # It was deleted or Axyn was removed
        return False

    if current_channel == original_channel:
        return True

    # All members of the current channel must be members of the original channel
    original_channel_members = _members_to_set(_channel_members(original_channel))
    current_channel_members = _members_to_set(_channel_members(current_channel))
    return current_channel_members.issubset(original_channel_members)

