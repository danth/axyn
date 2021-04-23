import logging
import numpy

from axyn.filters import reason_not_to_learn, reason_not_to_learn_pair


async def quantile_interval(bot, channel, quantile=0.5, default=None):
    """
    Compute a quantile of the reply time in the given channel.

    A default value can be given, which will be returned if no data is
    available.
    """

    logger = logging.getLogger(f"{__name__}.{channel.id}")

    intervals = await _get_intervals(bot, channel, logger)
    logger.info("Computing %.2fth quantile of %i intervals", quantile, len(intervals))

    if len(intervals) > 0:
        result = numpy.quantile(intervals, quantile)
        logger.info("The quantile is %.1f", result)
        return result
    else:
        logger.info("No data, using default value: %s", str(default))
        return default


async def _get_intervals(bot, channel, logger):
    """
    Calculate the delay in seconds between pairs of recent messages in a channel.

    To get more reliable data, this ignores any pairs which wouldn't be learned.
    """

    logger.info("Fetching up to 100 messages")
    history = await channel.history(
        limit=100,
        oldest_first=True,
    ).flatten()
    logger.info("Got %i messages", len(history))

    # [1, 2, 3, 4] -> [(1, 2), (2, 3), (3, 4)]
    pairs = zip(history, history[1:])

    intervals = []
    for a, b in pairs:
        # Use the learning filters to remove any unsuitable pairs
        if (
            not reason_not_to_learn(bot, b)
            and not reason_not_to_learn_pair(bot, a, b)
        ):
            # Calculate how many seconds passed between the two messages being sent
            interval = (b.created_at - a.created_at).total_seconds()
            intervals.append(interval)

    logger.info("Found %i reliable data points", len(intervals))
    return intervals
