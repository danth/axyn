from __future__ import annotations
from axyn.database import (
    ChannelRecord,
    ConsentPromptRecord,
    ConsentResponse,
    InteractionRecord,
    MessageRecord,
    MessageRevisionRecord,
    UserRecord,
)
from axyn.client import AxynClient
from axyn.managers.database import DatabaseManager
from axyn.managers.consent import ConsentManager
from datetime import datetime
from discord import (
    DMChannel,
    Interaction,
    InteractionResponse,
    InteractionCallbackResponse,
    Message,
    Member,
    User,
)
from discord.errors import Forbidden
from logging import DEBUG, INFO, WARNING
from pytest import fixture, mark
from sqlalchemy import select, func
from typing import TYPE_CHECKING
from unittest.mock import Mock


if TYPE_CHECKING:
    from pytest import LogCaptureFixture, MonkeyPatch


LOG_NAME = "axyn.managers.consent"


@fixture
async def database_manager(monkeypatch: MonkeyPatch, tmp_path: str):
    monkeypatch.setattr("axyn.database.DATA_DIRECTORY", tmp_path)

    client = AxynClient()
    database_manager = DatabaseManager(client)
    await database_manager.setup_hook()

    async with database_manager.session() as session:
        session.add(UserRecord(user_id=10, human=True))
        session.add(UserRecord(user_id=11, human=True))
        session.add(UserRecord(user_id=12, human=False))

        session.add(ChannelRecord(channel_id=20, guild_id=None))

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


async def test_set_response_no(
    database_manager: DatabaseManager,
    consent_manager: ConsentManager,
):
    async with database_manager.session() as session:
        interaction = InteractionRecord(
            interaction_id=50,
            user_id=10,
            message_id=42,
            channel_id=20,
            guild_id=None,
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


@fixture
async def consent_manager(database_manager: DatabaseManager):
    client = AxynClient()
    client.database_manager = database_manager

    consent_manager = ConsentManager(client)
    await consent_manager.setup_hook()

    return consent_manager


@mark.parametrize("response", (
    ConsentResponse.WITH_PRIVACY,
    ConsentResponse.WITHOUT_PRIVACY,
))
async def test_set_response_other(
    database_manager: DatabaseManager,
    consent_manager: ConsentManager,
    response: ConsentResponse,
):
    async with database_manager.session() as session:
        interaction = InteractionRecord(
            interaction_id=50,
            user_id=10,
            message_id=42,
            channel_id=20,
            guild_id=None,
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


async def test_send_introduction_from_dm(
    consent_manager: ConsentManager,
    database_manager: DatabaseManager,
    caplog: LogCaptureFixture,
):
    channel = Mock(DMChannel)
    channel.id = 20
    channel.guild = None

    message = Mock(Message)
    message.id = 10
    message.author.id = 30
    message.channel = channel
    message.reference = None
    message.flags.ephemeral = False
    message.created_at = datetime.now()

    user = Mock(User)
    user.id = 31
    user.bot = False
    user.system = False
    user.display_name = "DISPLAY_NAME"
    user.create_dm.return_value = channel
    user.send.return_value = message

    with caplog.at_level(DEBUG, logger=LOG_NAME):
        async with database_manager.session() as session:
            await consent_manager.send_introduction(session, user)
            await session.commit()

    user.send.assert_called_once()
    assert user.send.call_args.args == (
        (
            "**Hello DISPLAY_NAME :wave:**\n"
            "It seems like it's the first time we've met. "
            "I'm a retro chatbot that tries to hold a conversation using only "
            "messages I've seen in the past. "
            "May I take quotes from you for this purpose?"
        ),
    )
    assert list(user.send.call_args.kwargs.keys()) == ["view"]

    async with database_manager.session() as session:
        prompt = await session.get(ConsentPromptRecord, 10)
        assert prompt is not None

    assert caplog.record_tuples == [(
        LOG_NAME,
        INFO,
        "Sent an introduction message to user 31",
    )]


async def test_send_introduction_from_guild(
    consent_manager: ConsentManager,
    database_manager: DatabaseManager,
    caplog: LogCaptureFixture,
):
    channel = Mock(DMChannel)
    channel.id = 20
    channel.guild = None

    message = Mock(Message)
    message.id = 10
    message.author.id = 30
    message.channel = channel
    message.reference = None
    message.flags.ephemeral = False
    message.created_at = datetime.now()

    member = Mock(Member)
    member.id = 31
    member.bot = False
    member.system = False
    member.display_name = "DISPLAY_NAME"
    member.guild.name = "GUILD_NAME"
    member.create_dm.return_value = channel
    member.send.return_value = message

    with caplog.at_level(DEBUG, logger=LOG_NAME):
        async with database_manager.session() as session:
            await consent_manager.send_introduction(session, member)
            await session.commit()

    member.send.assert_called_once()
    assert member.send.call_args.args == (
        (
            "**Hello DISPLAY_NAME :wave:**\n"
            "You just messaged me in **GUILD_NAME**, and it seems like it's "
            "the first time we've met. "
            "I'm a retro chatbot that tries to hold a conversation using only "
            "messages I've seen in the past. "
            "May I take quotes from you for this purpose?"
        ),
    )
    assert list(member.send.call_args.kwargs.keys()) == ["view"]

    async with database_manager.session() as session:
        prompt = await session.get(ConsentPromptRecord, 10)
        assert prompt is not None

    assert caplog.record_tuples == [(
        LOG_NAME,
        INFO,
        "Sent an introduction message to user 31",
    )]


async def test_send_introduction_to_bot(
    consent_manager: ConsentManager,
    database_manager: DatabaseManager,
    caplog: LogCaptureFixture,
):
    user = Mock(User)
    user.bot = True
    user.system = False

    with caplog.at_level(DEBUG, logger=LOG_NAME):
        async with database_manager.session() as session:
            await consent_manager.send_introduction(session, user)
            await session.commit()

    assert not user.create_dm.called
    assert not user.send.called

    async with database_manager.session() as session:
        prompt = await session.get(ConsentPromptRecord, 10)
        assert prompt is None

    assert caplog.record_tuples == []


async def test_send_introduction_to_system(
    consent_manager: ConsentManager,
    database_manager: DatabaseManager,
    caplog: LogCaptureFixture,
):
    user = Mock(User)
    user.bot = False
    user.system = True

    with caplog.at_level(DEBUG, logger=LOG_NAME):
        async with database_manager.session() as session:
            await consent_manager.send_introduction(session, user)
            await session.commit()

    assert not user.create_dm.called
    assert not user.send.called

    async with database_manager.session() as session:
        prompt = await session.get(ConsentPromptRecord, 10)
        assert prompt is None

    assert caplog.record_tuples == []


async def test_send_introduction_forbidden(
    consent_manager: ConsentManager,
    database_manager: DatabaseManager,
    caplog: LogCaptureFixture,
):
    channel = Mock(DMChannel)
    channel.id = 20
    channel.guild = None

    user = Mock(User)
    user.id = 30
    user.bot = False
    user.system = False
    user.create_dm.return_value = channel
    user.send.side_effect = Forbidden(Mock(), "Cannot DM user")

    with caplog.at_level(DEBUG, logger=LOG_NAME):
        async with database_manager.session() as session:
            await consent_manager.send_introduction(session, user)
            await session.commit()

    user.send.assert_called_once()

    async with database_manager.session() as session:
        prompt = await session.get(ConsentPromptRecord, 10)
        assert prompt is None

    assert caplog.record_tuples == [(
        LOG_NAME,
        WARNING,
        "Not allowed to send an introduction message to user 30",
    )]


async def test_send_menu(
    consent_manager: ConsentManager,
    database_manager: DatabaseManager,
    caplog: LogCaptureFixture,
):
    channel = Mock(DMChannel)
    channel.id = 20
    channel.guild = None

    message = Mock(Message)
    message.id = 10
    message.author.id = 30
    message.channel = channel
    message.reference = None
    message.flags.ephemeral = False
    message.created_at = datetime.now()

    callback_response = Mock(InteractionCallbackResponse)
    callback_response.resource = message

    response = Mock(InteractionResponse)
    response.send_message.return_value = callback_response

    user = Mock(User)
    user.id = 31
    user.bot = False
    user.system = False

    interaction = Mock(Interaction)
    interaction.response = response
    interaction.user = user

    with caplog.at_level(DEBUG, logger=LOG_NAME):
        async with database_manager.session() as session:
            await consent_manager.send_menu(session, interaction)
            await session.commit()

    response.send_message.assert_called_once()
    assert response.send_message.call_args.args == (
        "May I take quotes from you?",
    )
    assert list(response.send_message.call_args.kwargs.keys()) == [
        "ephemeral",
        "view",
    ]
    assert response.send_message.call_args.kwargs["ephemeral"]

    async with database_manager.session() as session:
        prompt = await session.get(ConsentPromptRecord, 10)
        assert prompt is not None

    assert caplog.record_tuples == [(
        LOG_NAME,
        INFO,
        "User 31 requested a consent menu",
    )]

