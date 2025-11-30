from __future__ import annotations
from axyn.database import (
    ConsentResponse,
    ConsentPromptRecord,
    ConsentResponseRecord,
    InteractionRecord,
    MessageRecord,
)
from discord import ButtonStyle, Member
from discord.errors import Forbidden
from discord.ui import View, button
from logging import getLogger
from sqlalchemy import select, desc, func
from typing import TYPE_CHECKING, cast


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from axyn.database import DatabaseManager
    from axyn.types import UserUnion
    from discord import Interaction, Message
    from discord.ui import Button
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

            message = cast(Message, response.resource)

            async with self._database.session() as session:
                await session.merge(ConsentPromptRecord(
                    message=MessageRecord.from_message(message)
                ))

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

        introduction = (
            f"**Hello {user.display_name} :wave:**\n"
            "You just messaged me"
        )

        if isinstance(user, Member):
            introduction += f" in **{user.guild}**"

        introduction += (
            ", and it seems like it's the first time we've met. "
            "I'm a retro chatbot that tries to hold a conversation using only "
            "messages I've seen in the past. "
            "May I take quotes from you for this purpose?\n"
            "- Any message I can see might be learned, even if you're talking "
            "to someone else.\n"
            "- Quotes will only be shared with people who can see the "
            "original channel.\n"
        )

        try:
            message = await user.send(introduction, view=ConsentMenu())
        except Forbidden:
            _logger.warning(f"Not allowed to send an introduction message to user {user.id}")
            return
        else:
            _logger.info(f"Sent an introduction message to user {user.id}")

        await session.merge(ConsentPromptRecord.from_message(message))

    async def send_introduction(self, session: AsyncSession, user: UserUnion):
        """
        Send a consent prompt to the given user if they haven't met Axyn
        before.
        """

        if await self._should_send_introduction(session, user):
            await self._send_introduction(session, user)

    async def set_response(self, interaction: Interaction, response: ConsentResponse):
        """Store a new ``ConsentResponse`` resulting from the given ``Interaction``."""

        _logger.info("User {interaction.user.id} changed their consent setting to {response}")

        async with self._database.session() as session:
            await session.merge(
                ConsentResponseRecord(
                    interaction=InteractionRecord.from_interaction(interaction),
                    response=response
                )
            )

    async def has_consented(self, user: UserUnion) -> bool:
        """
        Return whether the given user has allowed their messages to be learned.

        This is always ``True`` for bots.
        """

        if user.bot or user.system:
            return True

        async with self._database.session() as session:
            result = await session.execute(
                select(ConsentResponseRecord)
                .select_from(InteractionRecord)
                .join(ConsentResponseRecord.interaction)
                .where(InteractionRecord.user_id == user.id)
                .order_by(desc(InteractionRecord.created_at))
                .limit(1)
            )
            response_record = result.scalar()

            if response_record is None:
                return False

            return response_record.response == ConsentResponse.YES


class ConsentMenu(View):
    def __init__(self):
        super().__init__(timeout=None)

    @button(
        label="Accept",
        custom_id="consent:yes",
        style=ButtonStyle.primary
    )
    async def yes(self, interaction: Interaction, button: Button[View]):
        client = cast("AxynClient", interaction.client)

        await client.consent_manager.set_response(interaction, ConsentResponse.YES)

        await interaction.response.send_message(
            content="Thank you! I've turned on learning for your messages.",
            ephemeral=True
        )

    @button(
        label="Decline",
        custom_id="consent:no",
        style=ButtonStyle.secondary
    )
    async def no(self, interaction: Interaction, button: Button[View]):
        client = cast("AxynClient", interaction.client)

        await client.consent_manager.set_response(interaction, ConsentResponse.NO)

        await interaction.response.send_message(
            content=(
                "No problem! I've turned off learning for your messages. "
                "I'll still respond if you talk to me, but I won't record "
                "what you say."
            ),
            ephemeral=True
        )

