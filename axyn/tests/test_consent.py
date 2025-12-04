from __future__ import annotations
from axyn.database import (
    ChannelRecord,
    ConsentResponse,
    DatabaseManager,
    InteractionRecord,
    MessageRecord,
    MessageRevisionRecord,
    UserRecord,
)
from axyn.consent import (
    ConsentManager,
    ConsentMenu,
    ConsentSelect,
)
from collections import Counter
from datetime import datetime
from pytest import fixture, mark
from sqlalchemy import select, func
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pytest import MonkeyPatch


@fixture
async def database_manager(monkeypatch: MonkeyPatch, tmp_path: str):
    monkeypatch.setattr("axyn.database.DATA_DIRECTORY", tmp_path)

    database_manager = DatabaseManager()
    await database_manager.setup_hook()

    async with database_manager.write_session() as session:
        session.add(UserRecord(user_id=10, human=True))
        session.add(UserRecord(user_id=11, human=True))
        session.add(UserRecord(user_id=12, human=False))

        session.add(ChannelRecord(channel_id=20, guild_id=30))

        session.add(MessageRecord(
            message_id=40,
            author_id=10,
            channel_id=20,
            reference_id=None,
            created_at=datetime.fromisoformat("2025-12-02T22:26:43Z"),
            deleted_at=None,
        ))
        session.add(MessageRecord(
            message_id=41,
            author_id=11,
            channel_id=20,
            reference_id=40,
            created_at=datetime.fromisoformat("2025-12-02T22:27:34Z"),
            deleted_at=None,
        ))
        session.add(MessageRecord(
            message_id=42,
            author_id=12,
            channel_id=20,
            reference_id=40,
            created_at=datetime.fromisoformat("2025-12-02T22:32:00Z"),
            deleted_at=None,
        ))


        session.add(MessageRevisionRecord(
            message_id=40,
            edited_at=datetime.fromisoformat("2025-12-02T22:26:43Z"),
            content="Hello, world!",
        ))
        session.add(MessageRevisionRecord(
            message_id=40,
            edited_at=datetime.fromisoformat("2025-12-02T22:27:02"),
            content="This is an edit.",
        ))
        session.add(MessageRevisionRecord(
            message_id=41,
            edited_at=datetime.fromisoformat("2025-12-02T22:27:34Z"),
            content="I'm from someone else!",
        ))

        await session.commit()

    return database_manager


@fixture
def consent_manager(database_manager: DatabaseManager):
    return ConsentManager(
        None, # pyright: ignore[reportArgumentType]
        database_manager,
    )


async def test_set_response_no(
    database_manager: DatabaseManager,
    consent_manager: ConsentManager,
):
    async with database_manager.write_session() as session:
        interaction = InteractionRecord(
            interaction_id=50,
            user_id=10,
            message_id=42,
            channel_id=20,
            guild_id=30,
            created_at=datetime.fromisoformat("2025-12-02T22:32:59Z"),
        )
        session.add(interaction)

        await consent_manager.set_response(
            session,
            interaction,
            ConsentResponse.NO,
        )

        await session.commit() # Because get_response starts its own session
        new_response = await consent_manager.get_response(
            UserRecord(user_id=10, human=True)
        )
        assert new_response == ConsentResponse.NO

        count = await session.scalar(
            select(func.count())
            .select_from(MessageRevisionRecord)
            .join(MessageRecord)
            .where(MessageRecord.author_id == 10)
        )
        assert count == 0, "should delete the user's MessageRevisionRecords"

        count = await session.scalar(
            select(func.count())
            .select_from(MessageRevisionRecord)
            .join(MessageRecord)
            .where(MessageRecord.author_id != 10)
        )
        assert count == 1, "should not delete other MessageRevisionRecords"

        count = await session.scalar(
            select(func.count())
            .select_from(MessageRecord)
        )
        assert count == 3, "should not delete existing MessageRecords"


@mark.parametrize("response", (
    ConsentResponse.WITH_PRIVACY,
    ConsentResponse.WITHOUT_PRIVACY,
))
async def test_set_response_other(
    database_manager: DatabaseManager,
    consent_manager: ConsentManager,
    response: ConsentResponse,
):
    async with database_manager.write_session() as session:
        interaction = InteractionRecord(
            interaction_id=50,
            user_id=10,
            message_id=42,
            channel_id=20,
            guild_id=30,
            created_at=datetime.fromisoformat("2025-12-02T22:32:59Z"),
        )
        session.add(interaction)

        await consent_manager.set_response(session, interaction, response)

        await session.commit() # Because get_response starts its own session
        new_response = await consent_manager.get_response(
            UserRecord(user_id=10, human=True)
        )
        assert new_response == response

        count = await session.scalar(
            select(func.count())
            .select_from(MessageRevisionRecord)
        )
        assert count == 3, f"should not delete MessageRevisionRecords"

        count = await session.scalar(
            select(func.count())
            .select_from(MessageRecord)
        )
        assert count == 3, f"should not delete MessageRecords"


async def test_get_response_defaults_to_no_for_humans(
    consent_manager: ConsentManager,
):
    response = await consent_manager.get_response(
        UserRecord(user_id=10, human=True),
    )
    assert response == ConsentResponse.NO


async def test_get_response_defaults_to_with_privacy_for_bots(
    consent_manager: ConsentManager,
):
    response = await consent_manager.get_response(
        UserRecord(user_id=12, human=False),
    )
    assert response == ConsentResponse.WITH_PRIVACY


async def test_select_presents_all_options():
    select = ConsentSelect()

    values = Counter(option.value for option in select.options)
    responses = Counter(response.name for response in ConsentResponse)
    assert values == responses, "each ConsentResponse should appear exactly once"


async def test_select_has_different_labels():
    select = ConsentSelect()

    labels = Counter(option.label for option in select.options)
    for label, count in labels.items():
        assert count == 1, f'"{label}" should only appear once'


async def test_select_has_different_descriptions():
    select = ConsentSelect()

    descriptions = Counter(option.description for option in select.options)
    for description, count in descriptions.items():
        assert count == 1, f'"{description}" should only appear once'


async def test_menu_contains_select():
    menu = ConsentMenu()

    assert any(isinstance(child, ConsentSelect) for child in menu.children)

