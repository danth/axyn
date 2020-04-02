import discord
from discord.ext import commands, tasks

from models import Statement, Reaction


class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.status.start()

    def cog_unload(self):
        self.status.cancel()

    @tasks.loop(minutes=2)
    async def status(self):
        """Set the bot's status message to show a count of stored responses."""

        # Count stored statements and reactions
        session = self.bot.Session()
        statements = session.query(Statement).count()
        reactions = session.query(Reaction).count()
        session.close()

        # Set as status
        await self.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f'{statements} 💬 {reactions} 👍'
            )
        )

    @status.before_loop
    async def before_status(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Status(bot))
