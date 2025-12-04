from __future__ import annotations
from axyn.database import (
    ChannelRecord,
    DatabaseManager,
    MessageRecord,
    MessageRevisionRecord,
    UserRecord,
)
from axyn.filters import is_valid_prompt, is_valid_response
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

    database_manager = DatabaseManager()
    await database_manager.setup_hook()

    async with database_manager.write_session() as session:
        yield session


@fixture
async def normal_message(session: AsyncSession):
    session.add(UserRecord(user_id=20, human=True))
    session.add(ChannelRecord(channel_id=30, guild_id=None))

    message = MessageRecord(
        message_id=10,
        author_id=20,
        channel_id=30,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        deleted_at=None,
    )
    session.add(message)

    session.add(MessageRevisionRecord(
        message_id=10,
        edited_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        content="Hello, world!",
    ))

    return message


@fixture
async def bot_message(session: AsyncSession):
    session.add(UserRecord(user_id=20, human=False))
    session.add(ChannelRecord(channel_id=30, guild_id=None))

    message = MessageRecord(
        message_id=10,
        author_id=20,
        channel_id=30,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        deleted_at=None,
    )
    session.add(message)

    session.add(MessageRevisionRecord(
        message_id=10,
        edited_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        content="I am a robot",
    ))

    return message


@fixture
async def redacted_message(session: AsyncSession):
    session.add(UserRecord(user_id=20, human=True))
    session.add(ChannelRecord(channel_id=30, guild_id=None))

    message = MessageRecord(
        message_id=10,
        author_id=20,
        channel_id=30,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        deleted_at=None,
    )
    session.add(message)

    return message


@fixture
async def quickly_deleted_message(session: AsyncSession):
    session.add(UserRecord(user_id=20, human=True))
    session.add(ChannelRecord(channel_id=30, guild_id=None))

    message = MessageRecord(
        message_id=10,
        author_id=20,
        channel_id=30,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        deleted_at=datetime.fromisoformat("2025-12-03T13:40:02Z"),
    )
    session.add(message)

    session.add(MessageRevisionRecord(
        message_id=10,
        edited_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        content="Hello, world!",
    ))

    return message


@fixture
async def slowly_deleted_message(session: AsyncSession):
    session.add(UserRecord(user_id=20, human=True))
    session.add(ChannelRecord(channel_id=30, guild_id=None))

    message = MessageRecord(
        message_id=10,
        author_id=20,
        channel_id=30,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        deleted_at=datetime.fromisoformat("2025-12-03T13:45:00Z"),
    )
    session.add(message)

    session.add(MessageRevisionRecord(
        message_id=10,
        edited_at=datetime.fromisoformat("2025-12-03T13:40:00Z"),
        content="Hello, world!",
    ))

    return message


@fixture
async def response_message(session: AsyncSession):
    session.add(UserRecord(user_id=21, human=True))

    message = MessageRecord(
        message_id=11,
        author_id=21,
        channel_id=30,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        deleted_at=None,
    )
    session.add(message)

    session.add(MessageRevisionRecord(
        message_id=11,
        edited_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        content="Hi there :)",
    ))

    return message


@fixture
async def same_user_response_message(session: AsyncSession):
    message = MessageRecord(
        message_id=11,
        author_id=20,
        channel_id=30,
        reference_id=None,
        created_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        deleted_at=None,
    )
    session.add(message)

    session.add(MessageRevisionRecord(
        message_id=11,
        edited_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        content="Is anyone there?",
    ))

    return message


async def test_normal_message_is_valid_response(
    caplog: LogCaptureFixture,
    session: AsyncSession,
    normal_message: MessageRecord,
):
    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert await is_valid_response(session, normal_message)

    assert caplog.record_tuples == []


async def test_bot_message_is_invalid_response(
    caplog: LogCaptureFixture,
    session: AsyncSession,
    bot_message: MessageRecord,
):
    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert not await is_valid_response(session, bot_message)

    assert caplog.record_tuples == [(
        LOG_NAME,
        DEBUG,
        "10 is not valid because its author is not human",
    )]


async def test_redacted_message_is_invalid_response(
    caplog: LogCaptureFixture,
    session: AsyncSession,
    redacted_message: MessageRecord,
):
    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert not await is_valid_response(session, redacted_message)

    assert caplog.record_tuples == [(
        LOG_NAME,
        DEBUG,
        "10 is not valid because no revisions were saved",
    )]


async def test_deleted_message_is_valid_response(
    caplog: LogCaptureFixture,
    session: AsyncSession,
    slowly_deleted_message: MessageRecord,
):
    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert await is_valid_response(session, slowly_deleted_message)

    assert caplog.record_tuples == []


async def test_normal_message_is_valid_prompt(
    caplog: LogCaptureFixture,
    session: AsyncSession,
    response_message: MessageRecord,
    normal_message: MessageRecord,
):
    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert await is_valid_prompt(
            session,
            response_message,
            normal_message,
        )

    assert caplog.record_tuples == []


async def test_bot_message_is_valid_prompt(
    caplog: LogCaptureFixture,
    session: AsyncSession,
    response_message: MessageRecord,
    bot_message: MessageRecord,
):
    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert await is_valid_prompt(
            session,
            response_message,
            bot_message,
        )

    assert caplog.record_tuples == []


async def test_redacted_message_is_invalid_prompt(
    caplog: LogCaptureFixture,
    session: AsyncSession,
    response_message: MessageRecord,
    redacted_message: MessageRecord,
):
    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert not await is_valid_prompt(
            session,
            response_message,
            redacted_message,
        )

    assert caplog.record_tuples == [(
        LOG_NAME,
        DEBUG,
        "10 is not valid because no revisions were saved",
    )]


async def test_prompt_deleted_before_response_is_invalid(
    caplog: LogCaptureFixture,
    session: AsyncSession,
    response_message: MessageRecord,
    quickly_deleted_message: MessageRecord,
):
    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert not await is_valid_prompt(
            session,
            response_message,
            quickly_deleted_message,
        )

    assert caplog.record_tuples == [(
        LOG_NAME,
        DEBUG,
        "11 is not valid because 10 was deleted prior",
    )]


async def test_prompt_deleted_after_response_is_valid(
    caplog: LogCaptureFixture,
    session: AsyncSession,
    response_message: MessageRecord,
    slowly_deleted_message: MessageRecord,
):
    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert await is_valid_prompt(
            session,
            response_message,
            slowly_deleted_message,
        )

    assert caplog.record_tuples == []


async def test_same_user_prompt_is_invalid(
    caplog: LogCaptureFixture,
    session: AsyncSession,
    same_user_response_message: MessageRecord,
    normal_message: MessageRecord,
):
    with caplog.at_level(DEBUG, logger=LOG_NAME):
        assert not await is_valid_prompt(
            session,
            same_user_response_message,
            normal_message,
        )

    assert caplog.record_tuples == [(
        LOG_NAME,
        DEBUG,
        "11 is not valid because 10 has the same author",
    )]

