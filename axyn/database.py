from __future__ import annotations
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from axyn.types import is_supported_channel_type
from datetime import datetime
from enum import Enum
import os
from shutil import rmtree
from sqlalchemy import (
    Column,
    DateTime,
    Enum as EnumType,
    ForeignKey,
    UniqueConstraint,
    delete,
    desc,
    select,
    table,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.event import listen
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)
from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:
    from axyn.types import UserUnion
    from discord import Guild, Interaction, Message
    from sqlalchemy import Connection
    from sqlalchemy.engine.interfaces import DBAPIConnection
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.pool import ConnectionPoolEntry
    from typing import Any


DATA_DIRECTORY = "~/axyn"


def get_path(file: str) -> str:
    """Return the path of the given file within Axyn's data directory."""

    # Find path of data directory
    folder = os.path.expanduser(DATA_DIRECTORY)

    # Create directory if it doesn't exist
    os.makedirs(folder, exist_ok=True)

    return os.path.join(folder, file)


SCHEMA_VERSION: int = 10


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
    def from_user(user: UserUnion) -> UserRecord:
        """Create a ``UserRecord`` from the provided ``User``."""

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

    @staticmethod
    def from_channel(channel: Any) -> ChannelRecord:
        """
        Create a ``ChannelRecord`` from the provided channel.

        Raises an exception if the channel is of an unsupported type.
        """

        if not is_supported_channel_type(channel):
            raise TypeError(f"unsupported channel type: {type(channel)}")

        if channel.guild is None:
            guild_id = None
        else:
            guild_id = channel.guild.id

        return ChannelRecord(channel_id=channel.id, guild_id=guild_id)


class GuildRecord(BaseRecord):
    """Database record storing a guild we have seen."""

    __tablename__ = "guild"

    guild_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=False, # Should match Discord's ID
    )

    @staticmethod
    def from_guild(guild: Guild) -> GuildRecord:
        """Create a ``GuildRecord`` from the provided ``Guild``."""

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
    reference_id: Mapped[Optional[int]]
        # ^ No constraint because we may have missed the referenced message
    created_at: Mapped[datetime]
    deleted_at: Mapped[Optional[datetime]]

    @staticmethod
    def from_message(message: Message) -> MessageRecord:
        """
        Create a ``MessageRecord`` from the provided ``Message``.

        Raises an exception if the message is from a channel of an unsupported
        type.
        """

        if not is_supported_channel_type(message.channel):
            raise Exception(f"unsupported channel type: {type(message.channel)}")

        if message.reference is None:
            reference_id = None
        else:
            reference_id = message.reference.message_id

        return MessageRecord(
            message_id=message.id,
            author_id=message.author.id,
            channel_id=message.channel.id,
            reference_id=reference_id,
            created_at=message.created_at,
            deleted_at=None
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
    def from_message(message: Message) -> MessageRevisionRecord:
        """
        Create a ``MessageRevisionRecord`` from the provided ``Message``.

        Raises an exception if the message is from a channel of an unsupported
        type.
        """

        if message.edited_at is None:
            edited_at = message.created_at
        else:
            edited_at = message.edited_at

        return MessageRevisionRecord(
            message_id=message.id,
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
    def from_interaction(interaction: Interaction) -> InteractionRecord:
        """Create an ``InteractionRecord`` from the provided ``Interaction``."""

        if interaction.message is None:
            message_id = None
        else:
            message_id = interaction.message.id

        if interaction.channel is None:
            channel_id = None
        else:
            channel_id = interaction.channel.id

        if interaction.guild is None:
            guild_id = None
        else:
            guild_id = interaction.guild.id

        return InteractionRecord(
            interaction_id=interaction.id,
            user_id=interaction.user.id,
            message_id=message_id,
            channel_id=channel_id,
            guild_id=guild_id,
            created_at=interaction.created_at
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

class DatabaseManager:
    """Holds a connection to the database and controls database migrations."""

    def __init__(self):
        uri = "sqlite+aiosqlite:///" + get_path("database.sqlite3")

        engine = create_async_engine(uri)

        def on_connect(
            dbapi_connection: DBAPIConnection,
            connection_record: ConnectionPoolEntry,
        ):
            dbapi_connection.isolation_level = None

        listen(engine.sync_engine, "connect", on_connect)

        def on_begin(connection: Connection):
            # Enforce foreign key constraints.
            connection.exec_driver_sql("PRAGMA foreign_keys=1").close()

            # Use a write-ahead log to improve concurrency.
            connection.exec_driver_sql("PRAGMA journal_mode=WAL").close()

            # Begin the transaction.
            options = connection.get_execution_options()
            begin = "BEGIN " + options["transaction_mode"]
            connection.exec_driver_sql(begin).close()

            # Per-transaction setting, means that foreign key constraints are
            # delayed until COMMIT, so rows can be inserted in any order.
            # Must appear after BEGIN.
            connection.exec_driver_sql("PRAGMA defer_foreign_keys=1").close()

        listen(engine.sync_engine, "begin", on_begin)

        read_engine = engine.execution_options(transaction_mode="DEFERRED")
        write_engine = engine.execution_options(transaction_mode="IMMEDIATE")

        self.read_session = async_sessionmaker(bind=read_engine)
        self.write_session = async_sessionmaker(bind=write_engine)

    async def setup_hook(self):
        """Ensure the database is following the current schema."""

        async with self.write_session() as session:
            try:
                version = await session.scalar(
                    select(SchemaVersionRecord.schema_version)
                    .order_by(desc(SchemaVersionRecord.applied_at))
                    .limit(1)
                )
            except OperationalError:
                version = None

            if version is None:
                await self._create_new(session)
            else:
                await self._migrate(session, version)

            await session.commit()

    async def _create_new(self, session: AsyncSession):
        """Create a new database from a blank slate."""

        connection = await session.connection()
        await connection.run_sync(BaseRecord.metadata.create_all)

        session.add(SchemaVersionRecord(
            schema_version=SCHEMA_VERSION,
            applied_at=datetime.now(),
        ))

    async def _migrate(self, session: AsyncSession, version: int):
        """
        Migrate an existing database starting from the given version.

        Throws an exception if the current version is less than zero or greater
        than the current version.
        """

        if version == SCHEMA_VERSION:
            return

        if version < 0:
            raise Exception(f"database schema version {version} is not valid")

        if version > SCHEMA_VERSION:
            raise Exception(f"database schema version {version} is not supported ({SCHEMA_VERSION} is the newest supported)")

        connection = await session.connection()
        await connection.run_sync(self._migrate_operations, version)

        session.add(SchemaVersionRecord(
          schema_version=SCHEMA_VERSION,
          applied_at=datetime.now(),
        ))

    def _migrate_operations(self, connection: Connection, version: int):
        """Migrate an existing database starting from the given version."""

        context = MigrationContext.configure(connection)
        operations = Operations(context)

        if version < 4:
            with operations.batch_alter_table("message") as batch:
                batch.add_column(Column(
                    "deleted_at",
                    DateTime(),
                    nullable=True,
                ))

        if version < 8:
            # Change from {NO, YES} to {NO, WITH_PRIVACY, WITHOUT_PRIVACY}.
            # To do this, we need to temporarily use a type that contains all
            # four options, so that we can convert YES into WITH_PRIVACY while
            # both are valid.

            class Old(Enum):
                NO = 0
                YES = 1

            class Transition(Enum):
                NO = 0
                YES = 1
                WITH_PRIVACY = 2
                WITHOUT_PRIVACY = 3

            class New(Enum):
                NO = 0
                WITH_PRIVACY = 1
                WITHOUT_PRIVACY = 2

            with operations.batch_alter_table("consent_response") as batch:
                batch.alter_column(
                    "response",
                    existing_type=EnumType(Old),
                    existing_nullable=False,
                    type_=EnumType(Transition),
                    nullable=False,
                )

            transition_table = table(
                "consent_response",
                Column("response", EnumType(Transition), nullable=False),
                # Other columns omitted because they are not used below
            )

            operations.execute(
                transition_table
                .update()
                .where(transition_table.c.response == Transition.YES)
                .values(response=Transition.WITH_PRIVACY)
            )

            with operations.batch_alter_table("consent_response") as batch:
                batch.alter_column(
                    "response",
                    existing_type=EnumType(Transition),
                    existing_nullable=False,
                    type_=EnumType(New),
                    nullable=False,
                )

        if version < 9:
            # This only needs to happen once, even if we skipped over multiple
            # versions that would reset the index.
            self._reset_index(operations)

        if version < 10:
            batch_context = operations.batch_alter_table(
                "message",
                naming_convention={
                    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
                },
            )

            with batch_context as batch:
                batch.drop_constraint(
                    "fk_message_reference_id_message",
                    type_="foreignkey",
                )

    def _reset_index(self, operations: Operations):
        """
        Reset the index.

        This clears the index table in the database, and also removes the
        corresponding file on disk.

        This must be called before the ``IndexManager`` is loaded to avoid
        causing undefined behaviour.
        """

        operations.execute(delete(IndexRecord))

        rmtree(get_path("index"))

