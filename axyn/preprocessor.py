from __future__ import annotations
from logging import getLogger
from re import sub
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from re import Match


_logger = getLogger(__name__)


def preprocess_index(content: str) -> str:
    content = content.strip()

    _logger.debug(f'Preprocessed to "{content}"')

    return content


def preprocess_reply(
    content: str,
    *,
    original_prompt_author_id: int,
    original_response_author_id: int,
    current_prompt_author_id: int,
    axyn_id: int,
) -> str:
    _logger.debug(f'Original prompt author is {original_prompt_author_id}')
    _logger.debug(f'Original response author is {original_response_author_id}')
    _logger.debug(f'Current prompt author is {current_prompt_author_id}')
    _logger.debug(f'Axyn is {axyn_id}')

    content = content.strip()

    def replace_ping(match: Match[str]) -> str:
        if match.group(0) == f"<@{original_prompt_author_id}>":
            return f"<@{current_prompt_author_id}>"

        if match.group(0) == f"<@{original_response_author_id}>":
            return f"<@{axyn_id}>"

        if match.group(0) == f"<@{axyn_id}>":
            return "@everyone"

        return match.group(0)

    # Everything must be replaced in one pass, else we might replace a ping
    # more than once, if some of the arguments are the same.
    content = sub("<@[0-9]+>", replace_ping, content)

    _logger.debug(f'Preprocessed to "{content}"')

    return content

