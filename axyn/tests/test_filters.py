from __future__ import annotations
from axyn.client import AxynClient
from axyn.database import (
    ChannelRecord,
    MessageRecord,
    MessageRevisionRecord,
    UserRecord,
)
from axyn.filters import is_valid_pair
from axyn.managers.database import DatabaseManager
from datetime import datetime
from logging import DEBUG
from pytest import fixture
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pytest import LogCaptureFixture, MonkeyPatch
    from sqlalchemy.ext.asyncio import AsyncSession


LOG_NAME = "axyn.filters"


@fixture
async def session(monkeypatch: MonkeyPatch, tmp_path: str):
    monkeypatch.setattr("axyn.database.DATA_DIRECTORY", tmp_path)

    client = AxynClient()
    database_manager = DatabaseManager(client)
    await database_manager.setup_hook()

    async with database_manager.session() as session:
        yield session


async def test_human_replying_to_human_is_valid(
    caplog: LogCaptureFixture,
    session: AsyncSession,
):
    session.add(UserRecord(user_id=1, human=True))
    session.add(UserRecord(user_id=2, human=True))
    session.add(ChannelRecord(channel_id=1, guild_id=None))
    session.add(MessageRecord(
        message_id=1,
        author_id=1,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        deleted_at=None,
    ))
    prompt = MessageRevisionRecord(
        revision_id=1,
        message_id=1,
        edited_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        content="Hello, world!",
    )
    session.add(prompt)
    session.add(MessageRecord(
        message_id=2,
        author_id=2,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        deleted_at=None,
    ))
    response = MessageRevisionRecord(
        revision_id=2,
        message_id=2,
        edited_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        content="Hi there!",
    )
    session.add(response)

    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert await is_valid_pair(session, prompt, response)

    assert caplog.record_tuples == []


async def test_human_replying_to_self_is_invalid(
    caplog: LogCaptureFixture,
    session: AsyncSession,
):
    session.add(UserRecord(user_id=1, human=True))
    session.add(ChannelRecord(channel_id=1, guild_id=None))
    session.add(MessageRecord(
        message_id=1,
        author_id=1,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        deleted_at=None,
    ))
    prompt = MessageRevisionRecord(
        revision_id=1,
        message_id=1,
        edited_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        content="Hello, world!",
    )
    session.add(prompt)
    session.add(MessageRecord(
        message_id=2,
        author_id=1,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        deleted_at=None,
    ))
    response = MessageRevisionRecord(
        revision_id=2,
        message_id=2,
        edited_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        content="Hi there!",
    )
    session.add(response)

    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert not await is_valid_pair(session, prompt, response)

    assert caplog.record_tuples == [(
        LOG_NAME,
        DEBUG,
        "(1, 2) is not valid because both messages have the same author",
    )]


async def test_blank_prompt_is_invalid(
    caplog: LogCaptureFixture,
    session: AsyncSession,
):
    session.add(UserRecord(user_id=1, human=True))
    session.add(UserRecord(user_id=2, human=True))
    session.add(ChannelRecord(channel_id=1, guild_id=None))
    session.add(MessageRecord(
        message_id=1,
        author_id=1,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        deleted_at=None,
    ))
    prompt = MessageRevisionRecord(
        revision_id=1,
        message_id=1,
        edited_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        content="",
    )
    session.add(prompt)
    session.add(MessageRecord(
        message_id=2,
        author_id=2,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        deleted_at=None,
    ))
    response = MessageRevisionRecord(
        revision_id=2,
        message_id=2,
        edited_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        content="Hi there!",
    )
    session.add(response)

    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert not await is_valid_pair(session, prompt, response)

    assert caplog.record_tuples == [(
        LOG_NAME,
        DEBUG,
        "(1, 2) is not valid because one of the messages is blank",
    )]


async def test_blank_response_is_invalid(
    caplog: LogCaptureFixture,
    session: AsyncSession,
):
    session.add(UserRecord(user_id=1, human=True))
    session.add(UserRecord(user_id=2, human=True))
    session.add(ChannelRecord(channel_id=1, guild_id=None))
    session.add(MessageRecord(
        message_id=1,
        author_id=1,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        deleted_at=None,
    ))
    prompt = MessageRevisionRecord(
        revision_id=1,
        message_id=1,
        edited_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        content="Hello, world!",
    )
    session.add(prompt)
    session.add(MessageRecord(
        message_id=2,
        author_id=2,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        deleted_at=None,
    ))
    response = MessageRevisionRecord(
        revision_id=2,
        message_id=2,
        edited_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        content="",
    )
    session.add(response)

    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert not await is_valid_pair(session, prompt, response)

    assert caplog.record_tuples == [(
        LOG_NAME,
        DEBUG,
        "(1, 2) is not valid because one of the messages is blank",
    )]


async def test_human_replying_to_bot_is_valid(
    caplog: LogCaptureFixture,
    session: AsyncSession,
):
    session.add(UserRecord(user_id=1, human=False))
    session.add(UserRecord(user_id=2, human=True))
    session.add(ChannelRecord(channel_id=1, guild_id=None))
    session.add(MessageRecord(
        message_id=1,
        author_id=1,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        deleted_at=None,
    ))
    prompt = MessageRevisionRecord(
        revision_id=1,
        message_id=1,
        edited_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        content="Hello, world!",
    )
    session.add(prompt)
    session.add(MessageRecord(
        message_id=2,
        author_id=2,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        deleted_at=None,
    ))
    response = MessageRevisionRecord(
        revision_id=2,
        message_id=2,
        edited_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        content="Hi there!",
    )
    session.add(response)

    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert await is_valid_pair(session, prompt, response)

    assert caplog.record_tuples == []


async def test_bot_replying_to_human_is_invalid(
    caplog: LogCaptureFixture,
    session: AsyncSession,
):
    session.add(UserRecord(user_id=1, human=True))
    session.add(UserRecord(user_id=2, human=False))
    session.add(ChannelRecord(channel_id=1, guild_id=None))
    session.add(MessageRecord(
        message_id=1,
        author_id=1,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        deleted_at=None,
    ))
    prompt = MessageRevisionRecord(
        revision_id=1,
        message_id=1,
        edited_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        content="Hello, world!",
    )
    session.add(prompt)
    session.add(MessageRecord(
        message_id=2,
        author_id=2,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        deleted_at=None,
    ))
    response = MessageRevisionRecord(
        revision_id=2,
        message_id=2,
        edited_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        content="Hi there!",
    )
    session.add(response)

    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert not await is_valid_pair(session, prompt, response)

    assert caplog.record_tuples == [(
        LOG_NAME,
        DEBUG,
        "(1, 2) is not valid because the responding author is not human",
    )]


async def test_deleted_response_is_valid(
    caplog: LogCaptureFixture,
    session: AsyncSession,
):
    session.add(UserRecord(user_id=1, human=True))
    session.add(UserRecord(user_id=2, human=True))
    session.add(ChannelRecord(channel_id=1, guild_id=None))
    session.add(MessageRecord(
        message_id=1,
        author_id=1,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        deleted_at=None,
    ))
    prompt = MessageRevisionRecord(
        revision_id=1,
        message_id=1,
        edited_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        content="Hello, world!",
    )
    session.add(prompt)
    session.add(MessageRecord(
        message_id=2,
        author_id=2,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        deleted_at=datetime.fromisoformat("2025-12-03T14:00:00Z"),
    ))
    response = MessageRevisionRecord(
        revision_id=2,
        message_id=2,
        edited_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        content="Hi there!",
    )
    session.add(response)

    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert await is_valid_pair(session, prompt, response)

    assert caplog.record_tuples == []


async def test_prompt_deleted_before_response_is_invalid(
    caplog: LogCaptureFixture,
    session: AsyncSession,
):
    session.add(UserRecord(user_id=1, human=True))
    session.add(UserRecord(user_id=2, human=True))
    session.add(ChannelRecord(channel_id=1, guild_id=None))
    session.add(MessageRecord(
        message_id=1,
        author_id=1,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        deleted_at=datetime.fromisoformat("2025-12-03T13:40:35Z"),
    ))
    prompt = MessageRevisionRecord(
        revision_id=1,
        message_id=1,
        edited_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        content="Hello, world!",
    )
    session.add(prompt)
    session.add(MessageRecord(
        message_id=2,
        author_id=2,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        deleted_at=None,
    ))
    response = MessageRevisionRecord(
        revision_id=2,
        message_id=2,
        edited_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        content="Hi there!",
    )
    session.add(response)

    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert not await is_valid_pair(session, prompt, response)

    assert caplog.record_tuples == [(
        LOG_NAME,
        DEBUG,
        "(1, 2) is not valid because the prompt was deleted before the response was created",
    )]


async def test_prompt_deleted_after_response_is_valid(
    caplog: LogCaptureFixture,
    session: AsyncSession,
):
    session.add(UserRecord(user_id=1, human=True))
    session.add(UserRecord(user_id=2, human=True))
    session.add(ChannelRecord(channel_id=1, guild_id=None))
    session.add(MessageRecord(
        message_id=1,
        author_id=1,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        deleted_at=datetime.fromisoformat("2025-12-03T13:42:00Z"),
    ))
    prompt = MessageRevisionRecord(
        revision_id=1,
        message_id=1,
        edited_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        content="Hello, world!",
    )
    session.add(prompt)
    session.add(MessageRecord(
        message_id=2,
        author_id=2,
        channel_id=1,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        deleted_at=None,
    ))
    response = MessageRevisionRecord(
        revision_id=2,
        message_id=2,
        edited_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        content="Hi there!",
    )
    session.add(response)

    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert await is_valid_pair(session, prompt, response)

    assert caplog.record_tuples == []

