from __future__ import annotations
from axyn.client import AxynClient
from axyn.database import (
    ChannelRecord,
    MessageRecord,
    UserRecord,
)
from axyn.history import analyze_delays
from axyn.managers.database import DatabaseManager
from datetime import datetime
from pytest import fixture, raises
from statistics import StatisticsError
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pytest import MonkeyPatch
    from sqlalchemy.ext.asyncio import AsyncSession


@fixture
async def session(monkeypatch: MonkeyPatch, tmp_path: str):
    monkeypatch.setattr("axyn.database.DATA_DIRECTORY", tmp_path)

    client = AxynClient()
    database_manager = DatabaseManager(client)
    await database_manager.setup_hook()

    async with database_manager.session() as session:
        yield session


async def test_analyze_delays(session: AsyncSession):
    session.add(UserRecord(user_id=1, human=True))
    session.add(UserRecord(user_id=2, human=True))
    session.add(ChannelRecord(channel_id=1, guild_id=None))
    session.add(MessageRecord(
        message_id=1,
        author_id=1,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:39:56Z"),
        deleted_at=None,
    ))
    session.add(MessageRecord(
        message_id=2,
        author_id=2,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        deleted_at=None,
    ))
    session.add(MessageRecord(
        message_id=3,
        author_id=1,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:43:13Z"),
        deleted_at=None,
    ))
    session.add(MessageRecord(
        message_id=4,
        author_id=2,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:46:47Z"),
        deleted_at=None,
    ))
    session.add(MessageRecord(
        message_id=5,
        author_id=1,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:47:00Z"),
        deleted_at=None,
    ))
    session.add(MessageRecord(
        message_id=6,
        author_id=2,
        channel_id=1,
        reference_id=3,
        created_at=datetime.fromisoformat("2025-12-03T15:00:00Z"),
        deleted_at=None,
    ))
    session.add(MessageRecord(
        message_id=7,
        author_id=1,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T15:04:32Z"),
        deleted_at=None,
    ))
    session.add(MessageRecord(
        message_id=8,
        author_id=2,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T15:04:36Z"),
        deleted_at=None,
    ))

    # Delays should be [4, 64, 214, 4607]

    assert await analyze_delays(session, 2) == (49, 139, 1312.25)


async def test_analyze_delays_with_empty_data(session: AsyncSession):
    with raises(StatisticsError):
        await analyze_delays(session, 2)
