from __future__ import annotations
from logging import getLogger
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.client import AxynClient


_logger = getLogger(__name__)


def preprocess(client: AxynClient, content: str) -> str:
    """Return a cleaned-up version of the given message contents."""

    # Strip off leading @Axyn if it exists
    axyn = client.axyn().mention
    if content.startswith(axyn):
        content = content[len(axyn) :]

    # Remove leading/trailing whitespace
    content = content.strip()

    _logger.debug(f'Preprocessed to "{content}"')

    return content

