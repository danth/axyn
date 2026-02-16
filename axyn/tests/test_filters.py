from __future__ import annotations
from axyn.client import AxynClient
from axyn.database import (
    ChannelRecord,
    MessageRecord,
    MessageRevisionRecord,
    UserRecord,
)
from axyn.filters import select_valid_pairs
from axyn.managers.database import DatabaseManager
from datetime import datetime
from pytest import fixture
from sqlalchemy import select
from sqlalchemy.orm import aliased
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


async def _is_valid_pair(
    session: AsyncSession,
    prompt: MessageRevisionRecord,
    response: MessageRevisionRecord,
) -> bool:
    prompt_revision = aliased(MessageRevisionRecord)
    response_revision = aliased(MessageRevisionRecord)

    valid = await session.scalar(
        select(
            select_valid_pairs(
                select(1)
                .select_from(prompt_revision)
                .select_from(response_revision)
                .where(prompt_revision.revision_id == prompt.revision_id)
                .where(response_revision.revision_id == response.revision_id),
                prompt_revision,
                response_revision,
            )
            .exists()
        )
    )
    assert valid is not None
    return valid


async def test_human_responding_to_human_is_valid(session: AsyncSession):
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

    assert await _is_valid_pair(session, prompt, response)


async def test_human_responding_to_self_is_invalid(session: AsyncSession):
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

    assert not await _is_valid_pair(session, prompt, response)


async def test_blank_prompt_is_invalid(session: AsyncSession):
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

    assert not await _is_valid_pair(session, prompt, response)


async def test_blank_response_is_invalid(session: AsyncSession):
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

    assert not await _is_valid_pair(session, prompt, response)


async def test_ephemeral_prompt_is_invalid(session: AsyncSession):
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
        ephemeral=True,
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

    assert not await _is_valid_pair(session, prompt, response)


async def test_ephemeral_response_is_invalid(session: AsyncSession):
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
        ephemeral=True,
    ))
    response = MessageRevisionRecord(
        revision_id=2,
        message_id=2,
        edited_at=datetime.fromisoformat("2025-12-03T13:41:00Z"),
        content="Hi there!",
    )
    session.add(response)

    assert not await _is_valid_pair(session, prompt, response)


async def test_human_responding_to_bot_is_valid(session: AsyncSession):
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

    assert await _is_valid_pair(session, prompt, response)


async def test_bot_responding_to_human_is_invalid(session: AsyncSession):
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

    assert not await _is_valid_pair(session, prompt, response)


async def test_deleted_response_is_valid(session: AsyncSession):
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

    assert await _is_valid_pair(session, prompt, response)


async def test_prompt_deleted_before_response_is_invalid(session: AsyncSession):
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

    assert not await _is_valid_pair(session, prompt, response)


async def test_prompt_deleted_after_response_is_valid(session: AsyncSession):
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

    assert await _is_valid_pair(session, prompt, response)

