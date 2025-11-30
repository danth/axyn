from axyn.database import ChannelRecord, MessageRecord
from datetime import datetime
from logging import getLogger
from statistics import quantiles
from typing import Sequence, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession


_logger = getLogger(__name__)


async def get_history(
    session: AsyncSession,
    channel_id: int,
    time: Optional[datetime] = None
) -> Sequence[MessageRecord]:
    """
    Queries a chunk of channel history from our database.

    If a time is provided, the history will be up to but not including that
    time. Otherwise, it will be the most recent history.

    The number of messages returned is unspecified.
    """

    if time is None:
        time = datetime.now()

    result = await session.execute(
        select(MessageRecord)
        .where(MessageRecord.channel_id == channel_id)
        .where(MessageRecord.created_at < time)
        .order_by(desc(MessageRecord.created_at))
        .limit(100)
    )
    return result.scalars().all()


async def get_delays(session: AsyncSession, history: Sequence[MessageRecord]) -> tuple[float, float, float]:
    """
    Given a contiguous chunk of channel history, analyse the delays.

    Raises ``StatisticsError`` if there was not enough information in the
    provided list to get a result.
    """

    # Group messages into consecutive pairs, and for valid pairs, calculate the
    # time in seconds between the messages being sent.
    delays = []

    for current, prompt in zip(history, history[1:]):
        if current.author_id == prompt.author_id:
            continue

        # Bots usually reply immediately, which skews the results.
        await session.refresh(current, ["author"])
        if not current.author.human:
            continue

        delay = (current.created_at - prompt.created_at).total_seconds()
        delays.append(delay)

    _logger.debug(f"Got {len(delays)} useful pairs from {len(history)} messages")

    lower, median, upper = quantiles(delays)

    _logger.debug(f"Quartiles are {lower}, {median}, {upper}")

    return lower, median, upper

