import logging

import numpy
from logdecorator.asyncio import async_log_on_start, async_log_on_end

from axyn.filters import reason_to_ignore_interval


@async_log_on_start(logging.DEBUG, "Computing {quantile}th quantile for channel {channel.id}")
@async_log_on_end(logging.DEBUG, "The quantile is {result}")
async def quantile_interval(client, channel, quantile=0.5, default=None):
    """
    Compute a quantile of the reply time in the given channel.

    A default value can be given, which will be returned if no data is
    available.
    """

    intervals = await _get_intervals(client, channel)

    if intervals:
        return numpy.quantile(intervals, quantile)

    return default


@async_log_on_end(logging.DEBUG, "Found the following datapoints: {result}")
async def _get_intervals(client, channel):
    """
    Calculate the delay in seconds between pairs of recent messages in a channel.

    To get more reliable data, this ignores any pairs which wouldn't be learned.
    """

    history = await _fetch_messages(channel)
    # [1, 2, 3, 4] -> [(1, 2), (2, 3), (3, 4)]
    pairs = zip(history, history[1:])

    intervals = []
    for a, b in pairs:
        if not reason_to_ignore_interval(client, a, b):
            # Calculate how many seconds passed between the two messages being sent
            interval = (b.created_at - a.created_at).total_seconds()
            intervals.append(interval)

    return intervals


@async_log_on_start(logging.DEBUG, "Fetching up to 100 messages")
@async_log_on_end(logging.DEBUG, "Finished fetching messages")
async def _fetch_messages(channel):
    """Fetch recent messages in a channel."""

    return await channel.history(limit=100, oldest_first=True).flatten()
