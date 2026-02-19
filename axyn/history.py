from __future__ import annotations
from axyn.database import MessageRecord
from opentelemetry.trace import get_tracer
from statistics import quantiles
from sqlalchemy import func, select
from sqlalchemy.orm import aliased
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


_tracer = get_tracer(__name__)


async def analyze_delays(
    session: AsyncSession,
    user_id: int
) -> tuple[float, float, float]:
    """
    Query the database for messages from the given user, and run statistics
    on how long they take to respond.
    """

    with _tracer.start_as_current_span(
        "analyze delays for user",
        attributes={"user.id": user_id},
    ) as span:
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
            .where(response.c.author_id == user_id)
            .where(response.c.ephemeral.is_not(True))
        )

        stream = await session.stream(query)

        try:
            delays = [
                (response_created_at - prompt_created_at).total_seconds()
                async for prompt_created_at, response_created_at in stream
            ]
        finally:
            await stream.close()

        lower, median, upper = quantiles(delays)

        span.set_attributes({
            "delays.count": len(delays),
            "delays.lower": lower,
            "delays.median": median,
            "delays.upper": upper,
        })

        return lower, median, upper

