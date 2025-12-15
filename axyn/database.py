from __future__ import annotations
from axyn.types import is_supported_channel_type
from datetime import datetime
from enum import Enum
import os
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)
from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:
    from axyn.types import UserUnion
    from discord import Guild, Interaction, Message
    from sqlalchemy.ext.asyncio import AsyncSession
    from typing import Any


DATA_DIRECTORY = "~/axyn"
SCHEMA_VERSION: int = 14


def get_path(file: str) -> str:
    """Return the path of the given file within Axyn's data directory."""

    # Find path of data directory
    folder = os.path.expanduser(DATA_DIRECTORY)

    # Create directory if it doesn't exist
    os.makedirs(folder, exist_ok=True)

    return os.path.join(folder, file)


class BaseRecord(DeclarativeBase):
    """Base class for database records."""


class SchemaVersionRecord(BaseRecord):
    """Database record storing the version of the database schema currently in use."""

    __tablename__ = "schema_version"

    schema_version: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=False, # Should match the hardcoded version ID
    )
    applied_at: Mapped[datetime]


class UserRecord(BaseRecord):
    """Database record storing a user we have seen."""

    __tablename__ = "user"

    user_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=False, # Should match Discord's ID
    )
    human: Mapped[bool]

    @staticmethod
    async def insert(session: AsyncSession, user: UserUnion):
        await session.execute(
            insert(UserRecord)
            .values(
                user_id=user.id,
                human=not (user.bot or user.system),
            )
            .on_conflict_do_nothing()
        )


class ChannelRecord(BaseRecord):
    """Database record storing a channel we have seen."""

    __tablename__ = "channel"

    channel_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=False, # Should match Discord's ID
    )
    guild_id: Mapped[Optional[int]] = mapped_column(ForeignKey("guild.guild_id"))

    @staticmethod
    async def insert(session: AsyncSession, channel: Any):
        if not is_supported_channel_type(channel):
            raise TypeError("unsupported channel type: {type(message.channel)}")

        if channel.guild is None:
            guild_id = None
        else:
            await GuildRecord.insert(session, channel.guild)
            guild_id = channel.guild.id

        await session.execute(
            insert(ChannelRecord)
            .values(
                channel_id=channel.id,
                guild_id=guild_id,
            )
            .on_conflict_do_nothing()
        )


class GuildRecord(BaseRecord):
    """Database record storing a guild we have seen."""

    __tablename__ = "guild"

    guild_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=False, # Should match Discord's ID
    )

    @staticmethod
    async def insert(session: AsyncSession, guild: Guild):
        await session.execute(
            insert(GuildRecord)
            .values(guild_id=guild.id)
            .on_conflict_do_nothing()
        )


class MessageRecord(BaseRecord):
    """
    Database record storing a message we have seen.

    This table only stores immutable metadata such as . Mutable content is
    stored in a related ``MessageRevisionRecord``.
    """

    __tablename__ = "message"

    message_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=False, # Should match Discord's ID
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("user.user_id"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channel.channel_id"))
    reference_id: Mapped[Optional[int]]
        # ^ No constraint because we may have missed the referenced message
    ephemeral: Mapped[Optional[bool]]
        # ^ Optional because we did not always store this flag
    created_at: Mapped[datetime]
    deleted_at: Mapped[Optional[datetime]]

    @staticmethod
    async def insert(session: AsyncSession, message: Message):
        await UserRecord.insert(session, message.author)
        await ChannelRecord.insert(session, message.channel)

        if message.reference is None:
            reference_id = None
        else:
            reference_id = message.reference.message_id

        await session.execute(
            insert(MessageRecord)
            .values(
                message_id=message.id,
                author_id=message.author.id,
                channel_id=message.channel.id,
                reference_id=reference_id,
                ephemeral=message.flags.ephemeral,
                created_at=message.created_at,
                deleted_at=None,

            )
            .on_conflict_do_nothing()
        )


class MessageRevisionRecord(BaseRecord):
    """
    Database record storing a message revision.

    This is a snapshot of the content of a message at a particular point in
    time.
    """

    __tablename__ = "message_revision"
    __table_args__ = (UniqueConstraint("message_id", "edited_at", name="unique_message_revision"),)

    revision_id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("message.message_id"))
    edited_at: Mapped[datetime]
    content: Mapped[str]

    @staticmethod
    async def insert(session: AsyncSession, message: Message):
        await MessageRecord.insert(session, message)

        if message.edited_at is None:
            edited_at = message.created_at
        else:
            edited_at = message.edited_at

        await session.execute(
            insert(MessageRevisionRecord)
            .values(
                message_id=message.id,
                edited_at=edited_at,
                content=message.content,
            )
            .on_conflict_do_nothing()
        )


class IndexRecord(BaseRecord):
    """
    Database record storing an indexed message.

    The index can be queried with a prompt to find the best matching reply, but
    it only returns an ID. This record maps that ID to a message containing the
    actual text. Each index ID may be mapped to more than one message (if we
    stored multiple replies to the same prompt), and those messages may also
    contain multiple edited versions to choose from.

    A message not having an ``IndexRecord`` means it has not been processed
    yet. This is different to having a record with an ``index_id`` of ``None``,
    which means we couldn't index it because there was no previous message.
    """

    __tablename__ = "index"

    message_id: Mapped[int] = mapped_column(
        ForeignKey("message.message_id"),
        primary_key=True,
    )
    index_id: Mapped[Optional[int]] = mapped_column(index=True)


class InteractionRecord(BaseRecord):
    """Database record storing an interaction we have recieved."""

    __tablename__ = "interaction"

    interaction_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=False, # Should match Discord's ID
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("user.user_id"))
    message_id: Mapped[Optional[int]] = mapped_column(ForeignKey("message.message_id"))
    channel_id: Mapped[Optional[int]] = mapped_column(ForeignKey("channel.channel_id"))
    guild_id: Mapped[Optional[int]] = mapped_column(ForeignKey("guild.guild_id"))
    created_at: Mapped[datetime]

    @staticmethod
    async def insert(session: AsyncSession, interaction: Interaction):
        if interaction.message is None:
            message_id = None
        else:
            await MessageRecord.insert(session, interaction.message)
            message_id = interaction.message.id

        if interaction.channel is None:
            channel_id = None
        else:
            await ChannelRecord.insert(session, interaction.channel)
            channel_id = interaction.channel.id

        if interaction.guild is None:
            guild_id = None
        else:
            await GuildRecord.insert(session, interaction.guild)
            guild_id = interaction.guild.id

        await session.execute(
            insert(InteractionRecord)
            .values(
                interaction_id=interaction.id,
                user_id=interaction.user.id,
                message_id=message_id,
                channel_id=channel_id,
                guild_id=guild_id,
                created_at=interaction.created_at
            )
            .on_conflict_do_nothing()
        )


class ConsentResponse(Enum):
    NO = 0
    WITH_PRIVACY = 1
    WITHOUT_PRIVACY = 2


class ConsentPromptRecord(BaseRecord):
    """Database record storing a consent prompt we have sent."""

    __tablename__ = "consent_prompt"

    message_id: Mapped[int] = mapped_column(
        ForeignKey("message.message_id"),
        primary_key=True,
    )


class ConsentResponseRecord(BaseRecord):
    """
    Database record storing a consent response we have recieved.

    We store historical interactions in addition to the current setting, in
    case they are useful for future reference.
    """

    __tablename__ = "consent_response"

    interaction_id: Mapped[int] = mapped_column(
        ForeignKey("interaction.interaction_id"),
        primary_key=True,
    )
    response: Mapped[ConsentResponse]
