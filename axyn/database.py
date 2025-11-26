from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime
from discord import (
    Guild,
    Interaction,
    Message,
    Member,
    User
)
from enum import Enum
import os
from sqlalchemy import (
    ForeignKey,
    UniqueConstraint,
    create_engine
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)
from typing import Optional


def get_path(file):
    """Return the path of the given file within Axyn's data directory."""

    # Find path of data directory
    folder = os.path.expanduser("~/axyn")
    # Create directory if it doesn't exist
    os.makedirs(folder, exist_ok=True)

    return os.path.join(folder, file)


class BaseRecord(DeclarativeBase):
    """Base class for database records."""


class UserRecord(BaseRecord):
    """Database record storing a user we have seen."""

    __tablename__ = "user"

    user_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=False, # Should match Discord's ID
    )
    human: Mapped[bool]

    messages: Mapped[list[MessageRecord]] = relationship(back_populates="author")
    interactions: Mapped[list[InteractionRecord]] = relationship(back_populates="user")

    @staticmethod
    def from_user(user: User | Member) -> UserRecord:
        return UserRecord(
            user_id=user.id,
            human=not (user.bot or user.system)
        )


class ChannelRecord(BaseRecord):
    """Database record storing a channel we have seen."""

    __tablename__ = "channel"

    channel_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=False, # Should match Discord's ID
    )
    guild_id: Mapped[Optional[int]] = mapped_column(ForeignKey("guild.guild_id"))

    guild: Mapped[GuildRecord] = relationship(back_populates="channels")

    messages: Mapped[list[MessageRecord]] = relationship(back_populates="channel")
    interactions: Mapped[list[InteractionRecord]] = relationship(back_populates="channel")

    @staticmethod
    def from_channel(channel) -> ChannelRecord:
        if channel.guild is None:
            guild = None
        else:
            guild = GuildRecord.from_guild(channel.guild)

        return ChannelRecord(channel_id=channel.id, guild=guild)


class GuildRecord(BaseRecord):
    """Database record storing a guild we have seen."""

    __tablename__ = "guild"

    guild_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=False, # Should match Discord's ID
    )

    channels: Mapped[list[ChannelRecord]] = relationship(back_populates="guild")
    interactions: Mapped[list[InteractionRecord]] = relationship(back_populates="guild")

    @staticmethod
    def from_guild(guild: Guild) -> GuildRecord:
        return GuildRecord(guild_id=guild.id)


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
    reference_id: Mapped[Optional[int]] = mapped_column(ForeignKey("message.message_id"))
    created_at: Mapped[datetime]

    author: Mapped[UserRecord] = relationship(back_populates="messages")
    channel: Mapped[ChannelRecord] = relationship(back_populates="messages")
    reference: Mapped[MessageRecord] = relationship(
        back_populates="references",
        # Because this relationship is self-referential, we need to tell
        # SQLAlchemy which way round it is.
        remote_side=[message_id]
    )

    references: Mapped[list[MessageRecord]] = relationship(back_populates="reference")
    revisions: Mapped[list[MessageRevisionRecord]] = relationship(back_populates="message")
    interactions: Mapped[list[InteractionRecord]] = relationship(back_populates="message")
    consent_prompt: Mapped[Optional[ConsentPromptRecord]] = relationship(back_populates="message")
    index: Mapped[Optional[IndexRecord]] = relationship(back_populates="message")

    @staticmethod
    def from_message(message: Message) -> MessageRecord:
        if message.reference is None:
            reference_id = None
        else:
            reference_id = message.reference.message_id

        return MessageRecord(
            message_id=message.id,
            author=UserRecord.from_user(message.author),
            channel=ChannelRecord.from_channel(message.channel),
            reference_id=reference_id,
            created_at=message.created_at
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

    message: Mapped[MessageRecord] = relationship(back_populates="revisions")

    @staticmethod
    def from_message(message: Message) -> MessageRevisionRecord:
        if message.edited_at is None:
            edited_at = message.created_at
        else:
            edited_at = message.edited_at

        return MessageRevisionRecord(
            message=MessageRecord.from_message(message),
            edited_at=edited_at,
            content=message.content
        )


class IndexRecord(BaseRecord):
    """
    Database record storing an indexed message.

    The index can be queried with a prompt to find the best matching reply, but
    it only returns an ID. This record maps that ID to a message containing the
    actual text. Each index ID may be mapped to more than one message (if we
    stored multiple replies to the same prompt), and those messages may also
    contain multiple edited versions to choose from.
    """

    __tablename__ = "index"

    message_id: Mapped[int] = mapped_column(
        ForeignKey("message.message_id"),
        primary_key=True,
    )
    index_id: Mapped[Optional[int]] = mapped_column(index=True)

    message: Mapped[MessageRecord] = relationship(back_populates="index")


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

    user: Mapped[UserRecord] = relationship(back_populates="interactions")
    message: Mapped[Optional[MessageRecord]] = relationship(back_populates="interactions")
    channel: Mapped[Optional[ChannelRecord]] = relationship(back_populates="interactions")
    guild: Mapped[Optional[GuildRecord]] = relationship(back_populates="interactions")

    consent_response: Mapped[Optional[ConsentResponseRecord]] = relationship(back_populates="interaction")

    @staticmethod
    def from_interaction(interaction: Interaction) -> InteractionRecord:
        if interaction.message is None:
            message = None
        else:
            message = MessageRecord.from_message(interaction.message)

        if interaction.channel is None:
            channel = None
        else:
            channel = ChannelRecord.from_channel(interaction.channel)

        if interaction.guild is None:
            guild = None
        else:
            guild = GuildRecord.from_guild(interaction.guild)

        return InteractionRecord(
            interaction_id=interaction.id,
            user=UserRecord.from_user(interaction.user),
            message=message,
            channel=channel,
            guild=guild,
            created_at=interaction.created_at
        )


class ConsentResponse(Enum):
    NO = "no"
    YES = "yes"


class ConsentPromptRecord(BaseRecord):
    """Database record storing a consent prompt we have sent."""

    __tablename__ = "consent_prompt"

    message_id: Mapped[int] = mapped_column(
        ForeignKey("message.message_id"),
        primary_key=True,
    )

    message: Mapped[MessageRecord] = relationship(back_populates="consent_prompt")

    @staticmethod
    def from_message(message: Message) -> ConsentPromptRecord:
        return ConsentPromptRecord(
            message=MessageRecord.from_message(message)
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

    interaction: Mapped[InteractionRecord] = relationship(back_populates="consent_response")


class DatabaseManager:
    """Holds a connection to the database and constructs database sessions."""

    def __init__(self):
        uri = "sqlite:///" + get_path("database.sqlite3")
        engine = create_engine(uri)
        BaseRecord.metadata.create_all(engine)
        self._session_maker = sessionmaker(bind=engine)

    @contextmanager
    def session(self):
        session = self._session_maker()
        session.begin()

        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()


