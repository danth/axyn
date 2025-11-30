from __future__ import annotations
from axyn.channel import channel_members
from axyn.database import MessageRecord
from axyn.types import is_supported_channel_type
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from axyn.types import ChannelUnion, UserUnion
    from typing import Sequence



def _members_to_set(users: Sequence[UserUnion]) -> set[int]:
    """
    Convert a list of members to a set of their IDs.

    Bot users are filtered out.
    """

    return set(user.id for user in users if not (user.bot or user.system))


def can_send_in_channel(client: AxynClient, message: MessageRecord, current_channel: ChannelUnion):
    """
    Return whether a message may be sent to a channel.

    This is only true if everyone who can view the current channel can also
    view the channel where the message was originally sent.
    """

    original_channel = client.get_channel(message.channel_id)

    if not is_supported_channel_type(original_channel):
        # The original channel was deleted, became inaccessible, or a message
        # from an unsupported channel type somehow got added to our database.
        return False

    if current_channel == original_channel:
        return True

    # All members of the current channel must be members of the original channel
    original_channel_members = _members_to_set(channel_members(original_channel))
    current_channel_members = _members_to_set(channel_members(current_channel))
    return current_channel_members.issubset(original_channel_members)

