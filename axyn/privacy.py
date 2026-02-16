from __future__ import annotations
from axyn.channel import channel_members
from axyn.database import ConsentResponse, MessageRecord
from axyn.types import is_supported_channel_type
from opentelemetry.trace import get_tracer
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from axyn.types import ChannelUnion
    from sqlalchemy.ext.asyncio import AsyncSession


_tracer = get_tracer(__name__)


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

    with _tracer.start_as_current_span(
        "get consent to quote message",
        attributes={"message.id": message.message_id},
    ) as span:
        original_author = client.get_user(message.author_id)

        if original_author is None:
            span.add_event("Rejected because the original author was not found")
            return False

        consent_response = await client.consent_manager.get_response(session, original_author)

        if consent_response == ConsentResponse.WITHOUT_PRIVACY:
            span.add_event("Accepted because the original author consented without privacy")
            return True

        original_channel = client.get_channel(message.channel_id)

        if original_channel is None:
            span.add_event("Rejected because the original channel was not found")
            return False

        if not is_supported_channel_type(original_channel):
            span.add_event("Rejected because the original channel is an unsupported type")
            return False

        if current_channel == original_channel:
            span.add_event("Accepted because the current channel is original channel")
            return True

        # All members of the current channel must be members of the original channel
        original_members = set(channel_members(original_channel))

        for current_member in channel_members(current_channel):
            if current_member.bot or current_member.system:
                continue

            if current_member not in original_members:
                span.add_event(
                    "Rejected because the current channel has a member who "
                    "is not in the original channel"
                )
                return False

        span.add_event(
            "Accepted because all members of the current channel are members "
            "of the original channel"
        ) 
        return True

