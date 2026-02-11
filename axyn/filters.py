from __future__ import annotations
from axyn.database import UserRecord, MessageRecord, MessageRevisionRecord
from axyn.history import analyze_delays
from discord import ChannelType, MessageType, Message
from logging import getLogger
from sqlalchemy import select, desc
from statistics import StatisticsError
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from sqlalchemy.ext.asyncio import AsyncSession
    from typing import Optional


_logger = getLogger(__name__)


async def is_direct(client: AxynClient, message: Message) -> bool:
    """Return whether the given message appears to be talking to Axyn."""

    axyn = client.axyn()

    if message.channel.type == ChannelType.private:
        return True

    if "axyn" in getattr(message.channel, "name", ""):
        return True

    if axyn.mentioned_in(message):
        return True

    async with client.database_manager.session() as session:
        current_message = await session.get_one(MessageRecord, message.id)

        if current_message.reference_id is not None:
            reference_author_id = await session.scalar(
                select(MessageRecord.author_id)
                .where(MessageRecord.message_id == current_message.reference_id)
            )

            return reference_author_id == axyn.id

        previous_message = await session.scalar(
            select(MessageRecord)
            .where(MessageRecord.channel_id == current_message.channel_id)
            .where(MessageRecord.created_at < current_message.created_at)
            .where(MessageRecord.ephemeral.is_not(True))
            .order_by(desc(MessageRecord.created_at))
            .limit(1)
        )

        if previous_message is None:
            return False

        # The below cannot be a WHERE clause because that would find the
        # previous Axyn message, rather than the previous message.
        if previous_message.author_id != axyn.id:
            return False

        try:
            _, _, upper_quartile = await analyze_delays(
                session,
                current_message.channel_id,
                current_message.created_at,
            )
        except StatisticsError:
            return False

        delay = (current_message.created_at - previous_message.created_at).total_seconds()

        return delay < upper_quartile


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

