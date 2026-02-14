from __future__ import annotations
from axyn.database import UserRecord, MessageRecord, MessageRevisionRecord
from discord import ChannelType, MessageType, Message
from logging import getLogger
from sqlalchemy import select
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from sqlalchemy.ext.asyncio import AsyncSession
    from typing import Optional


_logger = getLogger(__name__)


def is_direct(client: AxynClient, message: Message) -> bool:
    """Return whether the given message directly addresses Axyn."""

    axyn = client.axyn()

    return (
        message.channel.type == ChannelType.private or
        "axyn" in getattr(message.channel, "name", "") or
        axyn.mentioned_in(message) or
        (
            message.reference is not None and
            isinstance(message.reference.resolved, Message) and
            message.reference.resolved.author == axyn
        )
    )


async def is_valid_pair(
    session: AsyncSession,
    prompt: MessageRevisionRecord,
    response: MessageRevisionRecord,
) -> bool:
    """Return whether the given pair of revisions is learnable."""

    if not prompt.content or not response.content:
        _logger.debug(
            f"({prompt.revision_id}, {response.revision_id}) "
            "is not valid because one of the messages is blank"
        )
        return False

    human = await session.scalar(
        select(UserRecord.human)
        .join(MessageRecord)
        .where(MessageRecord.message_id == response.message_id)
    )

    if not human:
        _logger.debug(
            f"({prompt.revision_id}, {response.revision_id}) "
            "is not valid because the responding author is not human"
        )
        return False

    same_author = await session.scalar(
        select(
            select(MessageRecord.author_id)
            .where(MessageRecord.message_id == prompt.message_id)
            .scalar_subquery()
            ==
            select(MessageRecord.author_id)
            .where(MessageRecord.message_id == response.message_id)
            .scalar_subquery()
        )
    )

    if same_author:
        _logger.debug(
            f"({prompt.revision_id}, {response.revision_id}) "
            "is not valid because both messages have the same author"
        )
        return False

    deleted_prior = await session.scalar(
        select(
            select(MessageRecord.deleted_at)
            .where(MessageRecord.message_id == prompt.message_id)
            .scalar_subquery()
            <
            select(MessageRecord.created_at)
            .where(MessageRecord.message_id == response.message_id)
            .scalar_subquery()
        )
    )

    if deleted_prior:
        _logger.debug(
            f"({prompt.revision_id}, {response.revision_id}) "
            "is not valid because the prompt was deleted before the response was created"
        )
        return False

    return True


def reason_not_to_reply(message: Message) -> Optional[str]:
    """If the given message shouldn't be replied to, return a reason why."""

    if (
        message.type != MessageType.default and
        message.type != MessageType.reply
    ):
        return "this is not a regular message"

    if len(message.content) == 0:
        return "this message has no text"

    if message.author.bot or message.author.system:
        return "this message is authored by a bot"

