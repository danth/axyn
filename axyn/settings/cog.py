import discord
from discord.ext import commands

from axyn.settings.settings import ALL_SETTINGS


def cleanup_value(value):
    """Replace certain setting values with a more readable name."""

    if value is None:
        return "not set"

    if isinstance(value, bool):
        return "enabled" if value else "disabled"

    return value


class Settings(commands.Cog):
    def __init__(self, bot, settings):
        self.bot = bot

        for setting in settings:
            self._add_commands(setting)

    def _add_commands(self, setting):
        """Add all commands for the given setting."""

        @self.bot.group(
            cog=self,
            name=setting.name,
            help=(
                f"Show {setting.thing} in the current context.\n\n"
                "Subcommands are used to change this setting in different scopes."
            ),
        )
        async def group(ctx):
            if ctx.subcommand_passed is None:
                await self._show_value(ctx, setting)

        if setting.user_model:
            self._add_user_command(setting, group)

        if setting.channel_model:
            self._add_channel_command(setting, group)

        if setting.guild_model:
            self._add_guild_command(setting, group)

    def _add_user_command(self, setting, group):
        """Add a command to the given group to change the user setting."""

        @group.command(
            name="user",
            help=(
                f"Check or change your personal preference for {setting.thing}.\n\n"
                "Specify a new value to change the setting, "
                "otherwise this command will just show the current value."
            ),
        )
        async def change_user(ctx, new_value : setting.datatype = None):
            if new_value is None:
                await self._show_user_value(ctx, setting)
            else:
                setting.set_user_value(ctx.author, new_value)
                await self._show_user_value(ctx, setting, "is now")

    def _add_channel_command(self, setting, group):
        """Add a command to the given group to change the channel setting."""

        @group.command(
            name="channel",
            help=(
                f"Check or change {setting.thing} in this channel.\n\n"
                "Specify a new value to change the setting, "
                "otherwise this command will just show the current value."
            ),
        )
        @commands.guild_only()
        @commands.has_permissions(administrator=True)
        async def change_channel(ctx, new_value : setting.datatype = None):
            if new_value is None:
                await self._show_channel_value(ctx, setting)
            else:
                setting.set_channel_value(ctx.channel, new_value)
                await self._show_channel_value(ctx, setting, "is now")

    def _add_guild_command(self, setting, group):
        """Add a command to the given group to change the guild setting."""

        @group.command(
            name="server",
            aliases=["guild"],
            help=(
                f"Check or change {setting.thing} in this server.\n\n"
                "Specify a new value to change the setting, "
                "otherwise this command will just show the current value."
            ),
        )
        @commands.guild_only()
        @commands.has_permissions(administrator=True)
        async def change_guild(ctx, new_value : setting.datatype = None):
            if new_value is None:
                await self._show_guild_value(ctx, setting)
            else:
                setting.set_guild_value(ctx.guild, new_value)
                await self._show_guild_value(ctx, setting, "is now")

    async def _show_value(self, ctx, setting, connective="is"):
        """Show the effective value of the given setting."""

        value = setting.get_value(ctx.author, ctx.channel, ctx.guild)
        clean_value = cleanup_value(value)
        embed = discord.Embed(
            title=f"{setting.name.title()} {connective} {clean_value} here",
            colour=discord.Colour.blurple(),
        )

        if setting.user_model:
            user_value = setting.get_user_value(ctx.author)
            clean_user_value = cleanup_value(user_value)
            embed.add_field(name=ctx.author.display_name, value=clean_user_value, inline=False)

        if setting.channel_model:
            channel_value = setting.get_channel_value(ctx.channel)
            clean_channel_value = cleanup_value(channel_value)
            embed.add_field(name=f"#{ctx.channel.name}", value=clean_channel_value, inline=False)

        if setting.guild_model:
            guild_value = setting.get_guild_value(ctx.guild)
            clean_guild_value = cleanup_value(guild_value)
            embed.add_field(name=ctx.guild.name, value=clean_guild_value, inline=False)

        await ctx.send(embed=embed)

    async def _show_user_value(self, ctx, setting, connective="is"):
        """show the value of the given setting for the current user."""

        value = setting.get_user_value(ctx.author)
        clean_value = cleanup_value(value)

        embed = discord.Embed(
            description=f"{setting.name.title()} {connective} {clean_value} for {ctx.author.mention}",
            colour=discord.Colour.blurple(),
        )
        await ctx.send(embed=embed)

    async def _show_channel_value(self, ctx, setting, connective="is"):
        """show the value of the given setting for the current channel."""

        value = setting.get_channel_value(ctx.channel)
        clean_value = cleanup_value(value)

        embed = discord.Embed(
            description=f"{setting.name.title()} {connective} {clean_value} in {ctx.channel.mention}",
            colour=discord.Colour.blurple(),
        )
        await ctx.send(embed=embed)

    async def _show_guild_value(self, ctx, setting, connective="is"):
        """show the value of the given setting for the current guild."""

        value = setting.get_guild_value(ctx.guild)
        clean_value = cleanup_value(value)

        embed = discord.Embed(
            description=f"{setting.name.title()} {connective} {clean_value} in {ctx.guild.name}",
            colour=discord.Colour.blurple(),
        )
        await ctx.send(embed=embed)


def setup(bot):
    # All settings are made available on the bot instance for easy access
    bot.settings = {
        setting.name: setting(bot)
        for setting in ALL_SETTINGS
    }
    settings = bot.settings.values()

    bot.add_cog(Settings(bot, settings))
