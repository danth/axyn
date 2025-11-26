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
from discord.ext import tasks
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
from typing import cast


class ConsentManager:
    def __init__(self, client, database: DatabaseManager):
        self.client = client
        self._database = database

    def setup_hook(self):
        self._send_introductions.start()

        self.client.add_view(ConsentMenu())

        @self.client.command_tree.command()
        @async_log_on_start(logging.INFO, "{interaction.user.id} requested a consent menu")
        async def consent(interaction: Interaction):
            """Change whether Axyn learns from your messages."""

            response = await interaction.response.send_message(
                "May I learn from your messages?",
                ephemeral=True,
                view=ConsentMenu()
            )

            message = cast(Message, response.resource)

            with self._database.session() as session:
                session.merge(ConsentPromptRecord(
                    message=MessageRecord.from_message(message)
                ))

    async def _should_send_introduction(self, user: User, session: Session) -> bool:
        """Return whether a consent prompt should be sent to the given ``User``."""

        dm_channel = await user.create_dm()

        count = (
            session.query(ConsentPromptRecord)
            .select_from(MessageRecord)
            .join(ConsentPromptRecord.message)
            .where(MessageRecord.channel_id == dm_channel.id)
            .count()
        )

        return count == 0

    @async_log_on_start(logging.INFO, "Sending an introduction to {member.id}")
    @async_log_on_error(
        logging.WARNING,
        "Insufficient permissions to DM {member.id}",
        on_exceptions=Forbidden,
    )
    @async_log_on_end(logging.INFO, "Sent an introduction to {member.id}")
    async def _send_introduction(self, member: Member, session: Session):
        """Send a consent prompt to someone who hasn't met Axyn before."""

        message = await member.send(
            f"**Hello {member.display_name} :wave:**\n"
            f"I'm a robot who joins in with conversations in {member.guild}. "
"May I learn from what you say there?",
            view=ConsentMenu()
        )

        session.merge(ConsentPromptRecord.from_message(message))

    @tasks.loop(hours=1)
    @async_log_on_start(logging.INFO, "Checking for new members")
    @async_log_on_end(logging.INFO, "Finished checking for new members")
    async def _send_introductions(self):
        """Send introductions to all new members."""

        for member in self.client.get_all_members():
            if member.bot:
                continue

            with self._database.session() as session:
                if await self._should_send_introduction(member, session):
                    await self._send_introduction(member, session)

    @_send_introductions.before_loop
    async def _send_introductions_before(self):
        await self.client.wait_until_ready()

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

    def has_consented(self, user: User) -> bool:
        """Return whether the given ``User`` has allowed their messages to be learned."""

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
        label="Yes",
        custom_id="consent:yes",
        style=ButtonStyle.green
    )
    async def yes(self, interaction: Interaction, button: Button):
        interaction.client.consent_manager._set_response(interaction, ConsentResponse.YES)

        await interaction.response.send_message(
            content=(
                "Thanks! From now on, I'll remember some of your phrases. "
                "If you change your mind, type `/consent`."
            ),
            ephemeral=True
        )

    @button(
        label="No",
        custom_id="consent:no",
        style=ButtonStyle.red
    )
    async def no(self, interaction: Interaction, button: Button):
        interaction.client.consent_manager._set_response(interaction, ConsentResponse.NO)

        await interaction.response.send_message(
            content=(
                "No problem, I've turned off learning for you. "
                "You can enable it later by sending `/consent`."
            ),
            ephemeral=True
        )

