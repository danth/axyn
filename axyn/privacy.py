from __future__ import annotations
from axyn.channel import channel_members
from axyn.database import ConsentResponse, MessageRecord
from axyn.types import is_supported_channel_type
from logging import getLogger
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from axyn.types import ChannelUnion
    from sqlalchemy.ext.asyncio import AsyncSession


_logger = getLogger(__name__)


async def can_send_in_channel(
    client: AxynClient,
    session: AsyncSession,
    message: MessageRecord,
    current_channel: ChannelUnion,
):
    """
    Return whether a message may be sent to a channel.

    The behaviour of this depends on the original author's consent response.
    """

    original_author = client.get_user(message.author_id)

    if original_author is None:
        return False

    consent_response = await client.consent_manager.get_response(session, original_author)

    if consent_response == ConsentResponse.WITHOUT_PRIVACY:
        _logger.debug(
            "Privacy filter passed because original author "
            f"{original_author.id} gave consent response {consent_response}"
        )
        return True

    original_channel = client.get_channel(message.channel_id)

    if original_channel is None:
        _logger.debug(
            "Privacy filter failed because the original channel was not found"
        )
        return False

    if not is_supported_channel_type(original_channel):
        _logger.debug(
            "Privacy filter failed because the original channel "
            f"{original_channel.id} is of an unsupported type"
        )
        return False

    if current_channel == original_channel:
        _logger.debug(
            "Privacy filter passed because the current channel is the "
            "original channel"
        )
        return True

    # All members of the current channel must be members of the original channel
    original_members = set(channel_members(original_channel))

    for current_member in channel_members(current_channel):
        if current_member.bot or current_member.system:
            continue

        if current_member not in original_members:
            _logger.debug(
                f"Privacy filter failed because user {current_member.id} is "
                f"not a member of the original channel {original_channel.id}"
            )
            return False

    _logger.debug(
        "Privacy filter passed because all current channel members can see "
        f"the original channel {original_channel.id}"
    )
    return True

