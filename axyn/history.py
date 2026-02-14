from __future__ import annotations
from axyn.database import MessageRecord
from logging import getLogger
from statistics import quantiles
from sqlalchemy import func, select
from sqlalchemy.orm import aliased
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


_logger = getLogger(__name__)


async def analyze_delays(
    session: AsyncSession,
    user_id: int
) -> tuple[float, float, float]:
    """
    Query the database for messages from the given user, and run statistics
    on how long they take to reply.
    """

    prompt = aliased(MessageRecord, name="prompt")

    response = (
        select(
            MessageRecord,

            # LAG gets a value from the previous record, according to the
            # provided sort order.
            func
            .lag(MessageRecord.message_id)
            .over(
                order_by=MessageRecord.created_at,
                partition_by=MessageRecord.channel_id,
            )
            .label("previous_message_id"),
        )
        .where(MessageRecord.author_id == user_id)
        .where(MessageRecord.ephemeral.is_not(True))
        .subquery("response")
    )

    query = (
        select(
            prompt.created_at.label("prompt_created_at"),
            response.c.created_at.label("response_created_at"),
        )
        .join(
            prompt,
            prompt.message_id == func.coalesce(
                response.c.reference_id,
                response.c.previous_message_id,
            ),
        )
        .where(prompt.author_id != user_id)
        .where(prompt.ephemeral.is_not(True))
    )

    stream = await session.stream(query)

    try:
        delays = [
            (response_created_at - prompt_created_at).total_seconds()
            async for prompt_created_at, response_created_at in stream
        ]
    finally:
        await stream.close()

    _logger.debug(f"User {user_id}: Got {len(delays)} useful pairs")

    lower, median, upper = quantiles(delays)

    _logger.debug(f"User {user_id}: Quartiles are {lower}, {median}, {upper}")

    return lower, median, upper

