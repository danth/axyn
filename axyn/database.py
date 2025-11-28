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
from shutil import rmtree
from sqlalchemy import (
    ForeignKey,
    UniqueConstraint,
    create_engine,
    delete,
    desc,
    select,
)
from sqlalchemy.exc import NoResultFound, OperationalError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
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


SCHEMA_VERSION: int = 1


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
    """Holds a connection to the database and controls database migrations."""

    def __init__(self):
        uri = "sqlite:///" + get_path("database.sqlite3")
        engine = create_engine(uri)
        self._session_maker = sessionmaker(bind=engine)
        self._prepare()

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

    def _prepare(self):
        """Ensure the database is following the current schema."""

        with self.session() as session:
            try:
                version = (
                    session
                    .execute(
                        select(SchemaVersionRecord.schema_version)
                        .order_by(desc(SchemaVersionRecord.applied_at))
                        .limit(1)
                    )
                    .scalar_one()
                )
            except (OperationalError, NoResultFound):
                self._create_new(session)
            else:
                self._migrate_existing(session, version)

    def _create_new(self, session: Session):
        """Create a new database from a blank slate."""

        BaseRecord.metadata.create_all(session.connection())

        session.add(SchemaVersionRecord(
            schema_version=SCHEMA_VERSION,
            applied_at=datetime.now(),
        ))

    def _migrate_existing(self, session: Session, version: int):
        """
        Migrate an existing database starting from the given version.

        Throws an axception if the current version is less than zero or greated
        than the current version.
        """

        if version < 0:
            raise Exception(f"database schema version {version} is not valid")

        if version < 1:
            self._reset_index(session, 1)

        if version > SCHEMA_VERSION:
            raise Exception(f"database schema version {version} is not supported ({SCHEMA_VERSION} is the newest supported)")

    def _reset_index(self, session: Session, version: int):
        """
        Apply the provided schema version by resetting the index.

        This clears the index table in the database, and also removes the
        corresponding file on disk.

        This must be called before the ``IndexManager`` is loaded to avoid
        causing undefined behaviour.
        """

        session.connection().execute(delete(IndexRecord))

        rmtree(get_path("index"))

        session.add(SchemaVersionRecord(
          schema_version=version,
          applied_at=datetime.now(),
        ))

