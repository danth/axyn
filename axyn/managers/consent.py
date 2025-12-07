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
from axyn.managers import Manager
from axyn.ui.consent import ConsentMenu
from discord import Member
from discord.errors import Forbidden
from logging import getLogger
from sqlalchemy import delete, select, desc
from typing import TYPE_CHECKING, cast


if TYPE_CHECKING:
    from axyn.types import UserUnion
    from discord import Interaction, Message
    from sqlalchemy.ext.asyncio import AsyncSession
    from typing import Union


_logger = getLogger(__name__)


class ConsentManager(Manager):
    async def setup_hook(self):
        self._client.add_view(ConsentMenu())

        @self._client.command_tree.command()
        async def consent(interaction: Interaction): # pyright: ignore[reportUnusedFunction]
            """Change whether Axyn learns from your messages."""

            async with self._client.database_manager.write_session() as session:
                await self.send_menu(session, interaction)
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
                f"You just messaged me in **{user.guild.name}**, and it seems "
                "like it's the first time we've met. "
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

        _logger.info(f"Sent an introduction message to user {user.id}")

        await MessageRecord.insert(session, message)
        session.add(ConsentPromptRecord(message_id=message.id))

    async def send_introduction(self, session: AsyncSession, user: UserUnion):
        """
        Send a consent prompt to the given user if they haven't met Axyn
        before.
        """

        if await self._should_send_introduction(session, user):
            await self._send_introduction(session, user)

    async def send_menu(self, session: AsyncSession, interaction: Interaction):
        """Sent a consent menu in response to the given interaction."""

        _logger.info(f"User {interaction.user.id} requested a consent menu")

        response = await interaction.response.send_message(
            "May I take quotes from you?",
            ephemeral=True,
            view=ConsentMenu()
        )

        message = cast("Message", response.resource)

        await MessageRecord.insert(session, message)
        session.add(ConsentPromptRecord(message_id=message.id))

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

        async with self._client.database_manager.read_session() as session:
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

