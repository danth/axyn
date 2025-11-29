from axyn.database import (
    ConsentResponse,
    ConsentPromptRecord,
    ConsentResponseRecord,
    InteractionRecord,
    MessageRecord,
    DatabaseManager,
)
from discord import ButtonStyle, Interaction, Member, Message, User
from discord.errors import Forbidden
from discord.ui import View, Button, button
from logdecorator import log_on_end
from logdecorator.asyncio import (
    async_log_on_end,
    async_log_on_error,
    async_log_on_start,
)
import logging
from sqlalchemy import desc
from sqlalchemy.orm import Session
from typing import Union, cast


class ConsentManager:
    def __init__(self, client, database: DatabaseManager):
        self.client = client
        self._database = database

    def setup_hook(self):
        self.client.add_view(ConsentMenu())

        @self.client.command_tree.command()
        @async_log_on_start(logging.INFO, "{interaction.user.id} requested a consent menu")
        async def consent(interaction: Interaction):
            """Change whether Axyn learns from your messages."""

            response = await interaction.response.send_message(
                "May I take quotes from you?",
                ephemeral=True,
                view=ConsentMenu()
            )

            message = cast(Message, response.resource)

            with self._database.session() as session:
                session.merge(ConsentPromptRecord(
                    message=MessageRecord.from_message(message)
                ))

    async def _should_send_introduction(self, user: Union[User, Member], session: Session) -> bool:
        """Return whether a consent prompt should be sent to the given user."""

        if user.bot or user.system:
            return False

        dm_channel = await user.create_dm()

        count = (
            session.query(ConsentPromptRecord)
            .select_from(MessageRecord)
            .join(ConsentPromptRecord.message)
            .where(MessageRecord.channel_id == dm_channel.id)
            .count()
        )

        return count == 0

    @async_log_on_start(logging.INFO, "Sending an introduction to {user.id}")
    @async_log_on_error(
        logging.WARNING,
        "Insufficient permissions to DM {member.id}",
        on_exceptions=Forbidden,
    )
    @async_log_on_end(logging.INFO, "Sent an introduction to {user.id}")
    async def _send_introduction(self, user: Union[User, Member], session: Session):
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

        message = await user.send(
            introduction,
            view=ConsentMenu()
        )

        session.merge(ConsentPromptRecord.from_message(message))

    async def send_introduction(self, user: Union[User, Member], session: Session):
        """
        Send a consent prompt to the given user if they haven't met Axyn
        before.
        """

        if await self._should_send_introduction(user, session):
            await self._send_introduction(user, session)

    @log_on_end(
        logging.INFO, "User {interaction.user.id} changed their consent setting to {response}"
    )
    def _set_response(self, interaction: Interaction, response: ConsentResponse):
        """Store a new ``ConsentResponse`` resulting from the given ``Interaction``."""

        with self._database.session() as session:
            session.merge(
                ConsentResponseRecord(
                    interaction=InteractionRecord.from_interaction(interaction),
                    response=response
                )
            )

    def has_consented(self, user: Union[User, Member]) -> bool:
        """
        Return whether the given user has allowed their messages to be learned.

        This is always ``True`` for bots.
        """

        if user.bot or user.system:
            return True

        with self._database.session() as session:
            response_record = (
                session.query(ConsentResponseRecord)
                .select_from(InteractionRecord)
                .join(ConsentResponseRecord.interaction)
                .where(InteractionRecord.user_id == user.id)
                .order_by(desc(InteractionRecord.created_at))
                .limit(1)
                .one_or_none()
            )

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
    async def yes(self, interaction: Interaction, button: Button):
        interaction.client.consent_manager._set_response(interaction, ConsentResponse.YES)

        await interaction.response.send_message(
            content="Thank you! I've turned on learning for your messages.",
            ephemeral=True
        )

    @button(
        label="Decline",
        custom_id="consent:no",
        style=ButtonStyle.secondary
    )
    async def no(self, interaction: Interaction, button: Button):
        interaction.client.consent_manager._set_response(interaction, ConsentResponse.NO)

        await interaction.response.send_message(
            content=(
                "No problem! I've turned off learning for your messages. "
                "I'll still respond if you talk to me, but I won't record "
                "what you say."
            ),
            ephemeral=True
        )

