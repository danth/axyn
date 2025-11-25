from axyn.database import DatabaseManager, ConsentRecord
import discord
from discord.ext import tasks
from logdecorator import log_on_end
from logdecorator.asyncio import (
    async_log_on_end,
    async_log_on_error,
    async_log_on_start,
)
import logging


class ConsentManager:
    def __init__(self, client, database: DatabaseManager):
        self.client = client
        self._database = database

    def setup_hook(self):
        self._send_introductions.start()

        self.client.add_view(ConsentMenu())

        @self.client.command_tree.command()
        @async_log_on_start(logging.INFO, "{interaction.user.id} requested a consent menu")
        async def consent(interaction):
            """Change whether Axyn learns from your messages."""

            await interaction.response.send_message(
                "May I learn from your messages?",
                ephemeral=True,
                view=ConsentMenu()
            )

    async def send_introduction_menu(self, member):
        """Send a pair of buttons which allow consent to be changed."""

        await member.send(
            f"**Hello {member.display_name} :wave:**\n"
            f"I'm a robot who joins in with conversations in {member.guild}. "
            "May I learn from what you say there?",
            view=ConsentMenu()
        )

    @async_log_on_start(logging.INFO, "Sending an introduction to {member.id}")
    @async_log_on_error(
        logging.WARNING,
        "Insufficient permissions to DM {member.id}",
        on_exceptions=discord.errors.Forbidden,
    )
    @async_log_on_end(logging.INFO, "Sent an introduction to {member.id}")
    async def _send_introduction(self, member, session):
        """Send an introduction to someone who hasn't met Axyn before."""

        await self.send_introduction_menu(member)

        # Record an empty setting to signify that a menu was sent
        session.merge(ConsentRecord(user_id=member.id, consented=None))

    @tasks.loop(hours=1)
    @async_log_on_start(logging.INFO, "Checking for new members")
    @async_log_on_end(logging.INFO, "Finished checking for new members")
    async def _send_introductions(self):
        """Send introductions to all new members."""

        for member in self.client.get_all_members():
            if member.bot:
                continue

            with self._database.session() as session:
                setting = self._get_setting(member, session)

                if setting is None:
                    await self._send_introduction(member, session)

    @_send_introductions.before_loop
    async def _send_introductions_before(self):
        await self.client.wait_until_ready()

    def _get_setting(self, user, session):
        """Fetch the database entry for a user."""

        return (
            session.query(ConsentRecord)
            .where(ConsentRecord.user_id == user.id)
            .one_or_none()
        )

    @log_on_end(
        logging.INFO, "User {user_id} changed their consent setting to {consented}"
    )
    def _set_setting(self, user_id, consented):
        """Change the setting for a user."""

        with self._database.session() as session:
            session.merge(ConsentRecord(user_id=user_id, consented=consented))

    def has_consented(self, user):
        """Return whether a user has allowed their messages to be learned."""

        with self._database.session() as session:
            setting = self._get_setting(user, session)

            if setting is None:
                return False
            else:
                # The value might be None, so we must coerce it to a boolean
                return bool(setting.consented)


class ConsentMenu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Yes",
        custom_id="consent:yes",
        style=discord.ButtonStyle.green
    )
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        interaction.client.consent_manager._set_setting(interaction.user.id, True)

        await interaction.response.send_message(
            content=(
                "Thanks! From now on, I'll remember some of your phrases. "
                "If you change your mind, type `/consent`."
            ),
            ephemeral=True
        )

    @discord.ui.button(
        label="No",
        custom_id="consent:no",
        style=discord.ButtonStyle.red
    )
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        interaction.client.consent_manager._set_setting(interaction.user.id, False)

        await interaction.response.send_message(
            content=(
                "No problem, I've turned off learning for you. "
                "You can enable it later by sending `/consent`."
            ),
            ephemeral=True
        )

