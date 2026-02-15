from __future__ import annotations
from axyn.database import UserRecord, MessageRecord, MessageRevisionRecord
from discord import ChannelType, MessageType, Message
from logging import getLogger
from sqlalchemy import or_
from sqlalchemy.orm import aliased
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from sqlalchemy import Select
    from typing import Any, Optional


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


def select_valid_pairs[T: tuple[Any, ...]](
    query: Select[T],
    prompt_revision: type[MessageRevisionRecord],
    response_revision: type[MessageRevisionRecord],
) -> Select[T]:
    prompt_message = aliased(MessageRecord)
    response_message = aliased(MessageRecord)
    response_author = aliased(UserRecord)

    return (
        query
        .join(prompt_message, prompt_message.message_id == prompt_revision.message_id)
        .join(response_message, response_message.message_id == response_revision.message_id)
        .join(response_author, response_author.user_id == response_message.author_id)
        .where(prompt_revision.content != "")
        .where(response_revision.content != "")
        .where(prompt_message.ephemeral.is_not(True))
        .where(response_message.ephemeral.is_not(True))
        .where(prompt_message.author_id != response_message.author_id)
        .where(or_(
            prompt_message.deleted_at.is_(None),
            prompt_message.deleted_at > response_message.created_at,
        ))
        .where(response_author.human)
    )


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

