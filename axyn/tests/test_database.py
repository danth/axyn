from __future__ import annotations
from axyn.database import DatabaseManager, get_path
from datetime import datetime
from enum import Enum
from ngtpy import create as create_ngt
from pytest import fixture
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
)
from sqlalchemy.ext.asyncio import create_async_engine
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

