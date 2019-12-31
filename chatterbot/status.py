import discord
from discord.ext import commands, tasks


class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.status.start()

    def cog_unload(self):
        self.status.cancel()

    @tasks.loop(minutes=2)
    async def status(self):
        """
        Set the bot's status message to show a count of stored responses.

        The message will be in the format of "Listening to _ statements".
        """

        # Count stored statements
        count = self.bot.chatter.storage.count()

        # Set as status
        await self.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f'{count} statements'
            )
        )

    @status.before_loop
    async def before_status(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(Status(bot))
