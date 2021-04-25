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
                f"Show the effective setting for {setting.thing} here.\n\n"
                "Subcommands are used to change this setting in different scopes."
            ),
        )
        async def group(ctx):
            if ctx.subcommand_passed is None:
                await self._show_value(ctx, setting)

        for scope in setting.scopes:
            self._add_scope_command(setting, scope, group)

    def _add_scope_command(self, setting, scope, group):
        """Add a command for the given scope."""

        @group.command(
            name=scope.name,
            help=(
                f"Check or change {setting.thing} for this {scope.name}.\n\n"
                "Specify a new value to change the setting. "
                "Use this command with no arguments to view the current value."
            ),
        )
        @commands.check(scope.check)
        async def check_or_change(ctx, new_value : setting.datatype = None):
            if new_value is None:
                await self._show_scope_value(ctx, setting, scope.name)
            else:
                setting.set_value_in_scope(ctx, scope.name, new_value)
                await self._show_scope_value(ctx, setting, scope.name, "is now")

    async def _show_value(self, ctx, setting, connective="is"):
        """Show the effective value of the given setting."""

        value = setting.get_value(ctx)
        clean_value = cleanup_value(value)
        embed = discord.Embed(
            title=f"{setting.name.title()} {connective} {clean_value} here",
            colour=discord.Colour.blurple(),
        )

        for scope_name, value in setting.get_all_values(ctx).items():
            clean_value = cleanup_value(value)
            embed.add_field(name=scope_name.title(), value=clean_value, inline=False)

        await ctx.send(embed=embed)

    async def _show_scope_value(self, ctx, setting, scope_name, connective="is"):
        """Show the value of the given setting in the given scope."""

        value = setting.get_value_in_scope(ctx, scope_name)
        clean_value = cleanup_value(value)
        embed = discord.Embed(
            title=f"{setting.name.title()} {connective} {clean_value} for this {scope_name}",
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
