from __future__ import annotations
from axyn.database import (
    ConsentResponse,
    ConsentPromptRecord,
    ConsentResponseRecord,
    InteractionRecord,
    MessageRecord,
)
from discord import Member, SelectOption
from discord.errors import Forbidden
from discord.ui import Select, View
from logging import getLogger
from sqlalchemy import select, desc, func
from typing import TYPE_CHECKING, cast


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from axyn.database import DatabaseManager
    from axyn.types import UserUnion
    from discord import Interaction, Message
    from sqlalchemy.ext.asyncio import AsyncSession


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

    async def _should_send_introduction(self, session: AsyncSession, user: UserUnion) -> bool:
        """Return whether a consent prompt should be sent to the given user."""

        if user.bot or user.system:
            return False

        dm_channel = await user.create_dm()

        result = await session.execute(
            select(func.count())
            .select_from(ConsentPromptRecord)
            .join(MessageRecord)
            .where(MessageRecord.channel_id == dm_channel.id)
        )
        count = result.scalar_one()

        return count == 0

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

    async def set_response(self, interaction: Interaction, response: ConsentResponse):
        """Store a new ``ConsentResponse`` resulting from the given ``Interaction``."""

        _logger.info(f"User {interaction.user.id} changed their consent setting to {response}")

        async with self._database.session() as session:
            session.add(InteractionRecord.from_interaction(interaction))
            session.add(ConsentResponseRecord(
                interaction_id=interaction.id,
                response=response
            ))

    async def get_response(self, user: UserUnion) -> ConsentResponse:
        """
        Return whether the given user has allowed their messages to be learned.

        This is always ``ConsentResponse.WITHOUT_PRIVACY`` for bots.
        """

        if user.bot or user.system:
            return ConsentResponse.WITHOUT_PRIVACY

        async with self._database.session() as session:
            result = await session.execute(
                select(ConsentResponseRecord.response)
                .join(InteractionRecord)
                .where(InteractionRecord.user_id == user.id)
                .order_by(desc(InteractionRecord.created_at))
                .limit(1)
            )

            if response := result.scalar():
                return response
            else:
                return ConsentResponse.NO


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
        await client.consent_manager.set_response(interaction, self.selection)
        await interaction.response.send_message(
            "Setting changed.",
            ephemeral=True,
        )


class ConsentMenu(View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(ConsentSelect())

