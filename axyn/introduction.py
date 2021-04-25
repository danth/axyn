import asyncio
import logging

import discord
from discord.ext import commands, tasks

from axyn.models import IntroducedUser

# Set up logging
logger = logging.getLogger(__name__)


class Introduction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.send_introductions.start()

    def cog_unload(self):
        self.send_introductions.cancel()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Send an introduction message immediately after joining."""

        await self._introduce(member)

    @tasks.loop(hours=24)
    async def send_introductions(self):
        """Send introduction messages to any members who didn't get one when they joined."""

        logger.info("Checking for any missed introductions")

        await asyncio.gather(
            *(self._introduce(member) for member in self.bot.get_all_members())
        )

        logger.info("Missed introductions check finished")

    @send_introductions.before_loop
    async def send_introductions_before(self):
        """Wait until the bot is ready before sending introductions."""

        await self.bot.wait_until_ready()

    async def _introduce(self, member):
        """Send an introduction to the given user and record if it was successful."""

        if self._should_be_introduced(member):
            try:
                await self._send_introduction(member)
            except discord.Forbidden as error:
                logger.warning(
                    "Failed to send an introduction to %i: %s",
                    member.id,
                    error,
                )
            else:
                self._record_introduction(member)

    def _should_be_introduced(self, user):
        """Return whether the given user should recieve an introduction."""

        return not (user.bot or self._is_introduced(user))

    async def _send_introduction(self, member):
        """Send an introduction to the given user."""

        logger.info("Sending an introduction to %i", member.id)

        embed = discord.Embed(
            title=f"Hello {member.display_name} :wave: I'm Axyn",
            description=(
                "I'm a robot who joins in with human conversations. "
                f"I observe **{member.guild.name}** to help expand the topics "
                "I can chat about. If you don't mind me borrowing your "
                "phrases, please let me know by sending `a!learning user on`!"
            ),
            colour=discord.Colour.green(),
        )
        await member.send(embed=embed)

    def _record_introduction(self, user):
        """Note a successful introduction in the database."""

        session = self.bot.Session()
        session.add(IntroducedUser(id=user.id))
        session.commit()
        session.close()

        logger.info("Introduction to %i has been recorded as successful", user.id)

    def _is_introduced(self, user):
        """Return whether the given user has recieved an introduction before."""

        session = self.bot.Session()
        entry = (
            session.query(IntroducedUser)
            .filter(IntroducedUser.id == user.id)
            .one_or_none()
        )
        session.close()

        return entry is not None


def setup(bot):
    bot.add_cog(Introduction(bot))
