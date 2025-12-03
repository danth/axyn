from __future__ import annotations
from axyn.database import (
    ConsentResponse,
    ConsentPromptRecord,
    ConsentResponseRecord,
    InteractionRecord,
    MessageRecord,
    MessageRevisionRecord,
    UserRecord,
)
from discord import Member, SelectOption
from discord.errors import Forbidden
from discord.ui import Select, View
from logging import getLogger
from sqlalchemy import delete, select, desc
from typing import TYPE_CHECKING, cast


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from axyn.database import DatabaseManager
    from axyn.types import UserUnion
    from discord import Interaction, Message
    from sqlalchemy.ext.asyncio import AsyncSession
    from typing import Union


_logger = getLogger(__name__)


class ConsentManager:
    def __init__(self, client: AxynClient, database: DatabaseManager):
        self.client = client
        self._database = database

    async def setup_hook(self):
        self.client.add_view(ConsentMenu())

        @self.client.command_tree.command()
        async def consent(interaction: Interaction): # pyright: ignore[reportUnusedFunction]
            """Change whether Axyn learns from your messages."""

            _logger.info(f"User {interaction.user.id} requested a consent menu")

            response = await interaction.response.send_message(
                "May I take quotes from you?",
                ephemeral=True,
                view=ConsentMenu()
            )

            message = cast("Message", response.resource)

            async with self._database.session() as session:
                session.add(ConsentPromptRecord(message_id=message.id))

                await session.commit()

    async def _should_send_introduction(self, session: AsyncSession, user: UserUnion) -> bool:
        """Return whether a consent prompt should be sent to the given user."""

        if user.bot or user.system:
            return False

        dm_channel = await user.create_dm()

        exists = await session.scalar(select(
            select(ConsentPromptRecord)
            .join(MessageRecord)
            .where(MessageRecord.channel_id == dm_channel.id)
            .exists()
        ))
        assert exists is not None
        return not exists

    async def _send_introduction(self, session: AsyncSession, user: UserUnion):
        """Send a consent prompt to the given user."""

        introduction = f"**Hello {user.display_name} :wave:**\n"

        if isinstance(user, Member):
            introduction += (
                f"You just messaged me in **{user.guild}**, and it seems like "
                "it's the first time we've met. "
            )
        else:
            introduction += "It seems like it's the first time we've met. "

        introduction += (
            "I'm a retro chatbot that tries to hold a conversation using only "
            "messages I've seen in the past. "
            "May I take quotes from you for this purpose?"
        )

        try:
            message = await user.send(introduction, view=ConsentMenu())
        except Forbidden:
            _logger.warning(f"Not allowed to send an introduction message to user {user.id}")
            return
        else:
            _logger.info(f"Sent an introduction message to user {user.id}")

        session.add(ConsentPromptRecord(message_id=message.id))

    async def send_introduction(self, session: AsyncSession, user: UserUnion):
        """
        Send a consent prompt to the given user if they haven't met Axyn
        before.
        """

        if await self._should_send_introduction(session, user):
            await self._send_introduction(session, user)

    async def set_response(
        self,
        session: AsyncSession,
        interaction: InteractionRecord,
        response: ConsentResponse,
    ):
        """Store a new consent response resulting from the given interaction."""

        _logger.info(
            f"User {interaction.user_id} changed their consent setting "
            f"to {response}"
        )

        session.add(ConsentResponseRecord(
            interaction_id=interaction.interaction_id,
            response=response
        ))

        if response == ConsentResponse.NO:
            _logger.info(
                f"Redacting all messages from user {interaction.user_id}"
            )

            ids = await session.scalars(
                select(MessageRevisionRecord.revision_id)
                .join(MessageRecord)
                .where(MessageRecord.author_id == interaction.user_id)
            )

            await session.execute(
                delete(MessageRevisionRecord)
                .where(MessageRevisionRecord.revision_id.in_(ids))
            )

    async def get_response(self, user: Union[UserUnion, UserRecord]) -> ConsentResponse:
        """
        Return whether the given user has allowed their messages to be learned.

        This is always ``ConsentResponse.WITH_PRIVACY`` for bots. Depending on
        the bot, they might share private information about other users, so we
        should not leak it elsewhere.
        """

        if isinstance(user, UserRecord):
            user_id = user.user_id
            human = user.human
        else:
            user_id = user.id
            human = not (user.bot or user.system)

        if not human:
            return ConsentResponse.WITH_PRIVACY

        async with self._database.session() as session:
            response = await session.scalar(
                select(ConsentResponseRecord.response)
                .join(InteractionRecord)
                .where(InteractionRecord.user_id == user_id)
                .order_by(desc(InteractionRecord.created_at))
                .limit(1)
            )

            if response is None:
                return ConsentResponse.NO
            else:
                return response


class ConsentSelect(Select[View]):
    def __init__(self):
        super().__init__(
            custom_id="consent",
            options=[
                SelectOption(
                    label="Yes, share with anyone.",
                    value=ConsentResponse.WITHOUT_PRIVACY.name,
                    description=(
                        "Quotes can be used anywhere, including other servers. "
                        "Be careful not to share private information."
                    ),
                ),
                SelectOption(
                    label="Yes, share in the same community.",
                    value=ConsentResponse.WITH_PRIVACY.name,
                    description=(
                        "Quotes can be used if everyone in the channel has "
                        "access to the original message."
                    ),
                ),
                SelectOption(
                    label="No, don't store my messages.",
                    value=ConsentResponse.NO.name,
                    description=(
                        "Axyn will still respond to you, but won't remember "
                        "things you've said."
                    ),
                ),
            ],
            placeholder="Choose a setting",
        )

    @property
    def selection(self) -> ConsentResponse:
        return ConsentResponse[self.values[0]]

    async def callback(self, interaction: Interaction):
        client = cast("AxynClient", interaction.client)

        async with client.database_manager.session() as session:
            interaction_record = InteractionRecord.from_interaction(interaction)

            session.add(interaction_record)

            await client.consent_manager.set_response(
                session,
                interaction_record,
                self.selection,
            )

            await session.commit()

        await interaction.response.send_message(
            "Setting changed.",
            ephemeral=True,
        )


class ConsentMenu(View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(ConsentSelect())

