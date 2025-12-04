from __future__ import annotations
from asyncio import Event, TaskGroup, timeout
from axyn.database import (
    SCHEMA_VERSION,
    BaseRecord,
    ConsentPromptRecord,
    DatabaseManager,
    SchemaVersionRecord,
    UserRecord,
    get_path,
)
from datetime import datetime
from enum import Enum
from ngtpy import create as create_ngt
from os.path import exists
from pytest import fixture, mark, raises
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as EnumType,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pytest import MonkeyPatch


@fixture(autouse=True)
def temporary_database(monkeypatch: MonkeyPatch, tmp_path: str):
    monkeypatch.setattr("axyn.database.DATA_DIRECTORY", tmp_path)


@fixture
def schema_0() -> MetaData:
    """
    Version zero of the database schema.

    There were other, older schemas before this, but this is the first one
    where we started supporting migrations.
    """

    metadata = MetaData()

    Table(
        "schema_version",
        metadata,
        Column("schema_version", Integer(), nullable=False),
        Column("applied_at", DateTime(), nullable=False),
    )

    Table(
        "user",
        metadata,
        Column(
            "user_id",
            Integer(),
            nullable=False,
            primary_key=True,
            autoincrement=False,
        ),
        Column("human", Boolean(), nullable=False),
    )

    Table(
        "channel",
        metadata,
        Column(
            "channel_id",
            Integer(),
            nullable=False,
            primary_key=True,
            autoincrement=False,
        ),
        Column(
            "guild_id",
            Integer(),
            ForeignKey("guild.guild_id"),
            nullable=True,
        ),
    )

    Table(
        "guild",
        metadata,
        Column(
            "guild_id",
            Integer(),
            nullable=False,
            primary_key=True,
            autoincrement=False,
        ),
    )

    Table(
        "message",
        metadata,
        Column(
            "message_id",
            Integer(),
            nullable=False,
            primary_key=True,
            autoincrement=False,
        ),
        Column(
            "author_id",
            Integer(),
            ForeignKey("user.user_id"),
            nullable=False,
        ),
        Column(
            "channel_id",
            Integer(),
            ForeignKey("channel.channel_id"),
            nullable=False,
        ),
        Column(
            "reference_id",
            Integer(),
            ForeignKey("message.message_id"),
            nullable=False,
        ),
        Column("created_at", DateTime(), nullable=False),
    )

    Table(
        "message_revision",
        metadata,
        Column(
            "revision_id",
            Integer(),
            nullable=False,
            primary_key=True,
        ),
        Column(
            "message_id",
            Integer(),
            ForeignKey("message.message_id"),
            nullable=False,
        ),
        Column("edited_at", DateTime(), nullable=False),
        Column("content", String(), nullable=False),
    )

    Table(
        "index",
        metadata,
        Column(
            "message_id",
            Integer(),
            ForeignKey("message.message_id"),
            nullable=False,
            primary_key=True,
        ),
        Column("index_id", Integer(), nullable=False, index=True),
    )

    Table(
        "interaction",
        metadata,
        Column(
            "interaction_id",
            Integer(),
            nullable=False,
            primary_key=True,
            autoincrement=False,
        ),
        Column(
            "user_id",
            Integer(),
            ForeignKey("user.user_id"),
            nullable=False,
        ),
        Column(
            "message_id",
            Integer(),
            ForeignKey("message.message_id"),
            nullable=False,
        ),
        Column(
            "channel_id",
            Integer(),
            ForeignKey("channel.channel_id"),
            nullable=False,
        ),
        Column(
            "guild_id",
            Integer(),
            ForeignKey("guild.guild_id"),
            nullable=True,
        ),
        Column("created_at", DateTime(), nullable=False),
    )

    Table(
        "consent_prompt",
        metadata,
        Column(
            "message_id",
            Integer(),
            ForeignKey("message.message_id"),
            nullable=False,
            primary_key=True,
        ),
    )

    class Response(Enum):
        NO = 0
        YES = 1

    Table(
        "consent_response",
        metadata,
        Column(
            "interaction_id",
            Integer(),
            ForeignKey("interaction.interaction_id"),
            nullable=False,
            primary_key=True,
        ),
        Column("response", EnumType(Response), nullable=False),
    )

    return metadata


async def test_create_new():
    manager = DatabaseManager()
    await manager.setup_hook()


async def test_migrate_from_schema_0(schema_0: MetaData):
    uri = "sqlite+aiosqlite:///" + get_path("database.sqlite3")
    engine = create_async_engine(uri)

    async with engine.connect() as connection:
        await connection.run_sync(schema_0.create_all)

        await connection.execute(
            schema_0.tables["schema_version"]
            .insert()
            .values(
                schema_version=0,
                applied_at=datetime.now(),
            )
        )

        await connection.commit()

    create_ngt(get_path("index"), dimension=300)

    manager = DatabaseManager()
    await manager.setup_hook()


async def test_open_existing():
    uri = "sqlite+aiosqlite:///" + get_path("database.sqlite3")
    engine = create_async_engine(uri)
    session_maker = async_sessionmaker(engine)

    async with session_maker() as session:
        connection = await session.connection()
        await connection.run_sync(BaseRecord.metadata.create_all)

        session.add(SchemaVersionRecord(
            schema_version=SCHEMA_VERSION,
            applied_at=datetime.now(),
        ))

        await session.commit()

    manager = DatabaseManager()
    await manager.setup_hook()


@mark.parametrize("schema_version", (-1, SCHEMA_VERSION + 1))
async def test_open_invalid_schema(schema_version: int):
    uri = "sqlite+aiosqlite:///" + get_path("database.sqlite3")
    engine = create_async_engine(uri)
    session_maker = async_sessionmaker(engine)

    async with session_maker() as session:
        connection = await session.connection()
        await connection.run_sync(BaseRecord.metadata.create_all)

        session.add(SchemaVersionRecord(
            schema_version=schema_version,
            applied_at=datetime.now(),
        ))

        await session.commit()

    manager = DatabaseManager()

    with raises(Exception):
        await manager.setup_hook()


async def test_uses_write_ahead_log():
    manager = DatabaseManager()
    await manager.setup_hook()

    assert exists(get_path("database.sqlite3-shm"))
    assert exists(get_path("database.sqlite3-wal"))


async def test_foreign_key_constraints_are_checked():
    manager = DatabaseManager()
    await manager.setup_hook()

    async with manager.write_session() as session:
        session.add(ConsentPromptRecord(message_id=5))

        with raises(IntegrityError):
            await session.commit()


async def test_concurrent_writes_do_not_fail():
    # This checks that we do not encounter the situation described at
    # https://kerkour.com/sqlite-for-servers#use-immediate-transactions
    #
    # Usually it's a race condition, but in this test we synchronise the
    # tasks to force it to happen.

    manager = DatabaseManager()
    await manager.setup_hook()

    steal = Event()
    stolen = Event()

    async def victim():
        async with manager.write_session() as session:
            # Do a read statement to open a transaction.
            #
            # The desired behaviour is to open it in IMMEDIATE mode, locking
            # the database now, even though we haven't started writing yet.
            #
            # The default is to use DEFERRED mode, not locking the database
            # until we do a write statement.
            await session.execute(select(UserRecord))

            # Start the other task, then wait until it locks the database.
            #
            # If we used IMMEDIATE mode, the other task should start waiting
            # for us to finish our transaction. This deadlocks, so a timeout
            # will occur and we pass the test.
            #
            # If we used DEFERRED mode, the database is not locked yet, so the
            # other task would get the lock and we would continue running. If
            # we were to do a write statement after this, it would immediately
            # fail because the other task has the lock that we need.
            with raises(TimeoutError):
                async with timeout(0.5):
                    steal.set()
                    await stolen.wait()

    async def thief():
        await steal.wait()

        async with manager.write_session() as session:
            # Do a write statement to open a transaction, locking the database
            # regardless of what mode we used.
            session.add(UserRecord(user_id=2, human=True))
            await session.flush()

            # Tell the other task that we got the lock.
            stolen.set()

    async with TaskGroup() as group:
        group.create_task(victim())
        group.create_task(thief())

