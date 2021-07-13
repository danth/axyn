import logging
from contextlib import contextmanager

import discord
import sqlalchemy
from discord.ext import tasks
from discord_slash.model import ButtonStyle
from discord_slash.utils.manage_components import create_actionrow, create_button
from sqlalchemy import BigInteger, Boolean, Column
from sqlalchemy.ext.declarative import declarative_base
from logdecorator import log_on_start, log_on_end
from logdecorator.asyncio import async_log_on_start, async_log_on_end, async_log_on_error

from axyn.datastore import get_path

Base = declarative_base()


class UserConsent(Base):
    __tablename__ = "consent"
    user_id = Column(BigInteger, primary_key=True)
    consented = Column(Boolean)


def _format_button_id(user, consented):
    """Create a string which identifies a consent button."""

    choice = "yes" if consented else "no"
    return f"{user.id}-{choice}"


def _unpack_button_id(button_id):
    """Extract the user and choice from a button identifier."""

    user_id_string, choice = button_id.split("-")
    return int(user_id_string), choice == "yes"


class ConsentManager:
    @log_on_start(logging.INFO, "Opening consent database")
    def __init__(self, client):
        self.client = client

        self.client.slash.slash(
            name="consent", description="Change whether Axyn learns your messages."
        )(self.send_menu)

        database_url = "sqlite:///" + get_path("consent.sqlite3")
        engine = sqlalchemy.create_engine(database_url)

        Base.metadata.create_all(engine)

        self.Session = sqlalchemy.orm.sessionmaker(bind=engine)

        self._send_introductions.start()

    @contextmanager
    def _database_session(self):
        session = self.Session()
        session.begin()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()

    @async_log_on_start(logging.INFO, "{ctx.author.id} requested a consent menu")
    async def send_menu(self, ctx):
        """Send a pair of buttons which allow consent to be changed."""

        await ctx.send(
            "May I learn from your messages?",
            hidden=True,
            components=[
                create_actionrow(
                    create_button(
                        style=ButtonStyle.green,
                        label="Yes",
                        custom_id=_format_button_id(ctx.author, True),
                    ),
                    create_button(
                        style=ButtonStyle.red,
                        label="No",
                        custom_id=_format_button_id(ctx.author, False),
                    ),
                )
            ],
        )

    async def send_introduction_menu(self, member):
        """Send a pair of buttons which allow consent to be changed."""

        await member.send(
            f"**Hello {member.display_name} :wave:**\n"
            f"I'm a robot who joins in with conversations in {member.guild}. "
            "May I learn from what you say there?",
            components=[
                create_actionrow(
                    create_button(
                        style=ButtonStyle.green,
                        label="Yes",
                        custom_id=_format_button_id(member, True),
                    ),
                    create_button(
                        style=ButtonStyle.red,
                        label="No",
                        custom_id=_format_button_id(member, False),
                    ),
                )
            ],
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
        session.merge(UserConsent(user_id=member.id, consented=None))

    @tasks.loop(hours=1)
    @async_log_on_start(logging.INFO, "Checking for new members")
    @async_log_on_end(logging.INFO, "Finished checking for new members")
    async def _send_introductions(self):
        """Send introductions to all new members."""

        for member in self.client.get_all_members():
            if member.bot:
                continue

            with self._database_session() as session:
                setting = self._get_setting(member, session)
                if setting is None:
                    await self._send_introduction(member, session)

    @_send_introductions.before_loop
    async def _send_introductions_before(self):
        await self.client.wait_until_ready()

    async def handle_button(self, ctx):
        """Change a user's consent setting in response to an interaction."""

        user_id, consented = _unpack_button_id(ctx.custom_id)

        self._set_setting(user_id, consented)

        if consented:
            await ctx.send(
                content=(
                    "Thanks! From now on, I'll remember some of your phrases. "
                    "If you change your mind, type `/consent`."
                ),
                hidden=True,
            )
        else:
            await ctx.send(
                content=(
                    "No problem, I've turned off learning for you. "
                    "You can enable it later by sending `/consent`."
                ),
                hidden=True,
            )

    def _get_setting(self, user, session):
        """Fetch the database entry for a user."""

        return (
            session.query(UserConsent)
            .where(UserConsent.user_id == user.id)
            .one_or_none()
        )

    @log_on_end(logging.INFO, "User {user_id} changed their consent setting to {consented}")
    def _set_setting(self, user_id, consented):
        """Change the setting for a user."""

        with self._database_session() as session:
            session.merge(UserConsent(user_id=user_id, consented=consented))

    def has_consented(self, user):
        """Return whether a user has allowed their messages to be learned."""

        with self._database_session() as session:
            setting = self._get_setting(user, session)

            if setting is None:
                return False
            else:
                # The value might be None, so we must coerce it to a boolean
                return bool(setting.consented)
