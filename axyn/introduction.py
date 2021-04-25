import discord
from discord.ext import commands


class Introduction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Send an introduction message to new members."""

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


def setup(bot):
    bot.add_cog(Introduction(bot))
