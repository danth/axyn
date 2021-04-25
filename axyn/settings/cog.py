import discord
from discord.ext import commands

from axyn.settings.context import SettingContext
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
                f"Show {setting.thing} here.\n\n"
                "This setting can be changed in various scopes using the subcommands. "
                + setting.merge_values_help
            ),
        )
        async def group(ctx):
            if ctx.subcommand_passed is None:
                context = SettingContext.from_context(ctx)
                await self._show_value(ctx, context, setting)

        for scope in setting.scopes:
            self._add_scope_command(setting, scope, group)

    def _add_scope_command(self, setting, scope, group):
        """Add a command for the given scope."""

        @group.command(
            name=scope.name,
            help=(
                f"Control {setting.thing} for your current {scope.name}.\n\n"
                "Use this command with no arguments to view the current setting; "
                "specify a new value to change it."
            ),
        )
        @commands.check(scope.check)
        async def check_or_change(ctx, new_value: setting.datatype = None):
            context = SettingContext.from_context(ctx)

            if new_value is None:
                await self._show_scope_value(ctx, context, setting, scope.name)
            else:
                setting.set_value_in_scope(context, scope.name, new_value)
                await self._show_scope_value(
                    ctx, context, setting, scope.name, "is now"
                )

    async def _show_value(self, ctx, context, setting, connective="is"):
        """Show the effective value of the given setting."""

        value = setting.get_value(context)
        clean_value = cleanup_value(value)
        embed = discord.Embed(
            title=f"{setting.name.title()} {connective} {clean_value} here",
            description=setting.merge_values_help,
            colour=discord.Colour.blurple(),
        )

        for scope_name, value in setting.get_all_values(context).items():
            clean_value = cleanup_value(value)
            embed.add_field(name=scope_name.title(), value=clean_value, inline=False)

        await ctx.send(embed=embed)

    async def _show_scope_value(
        self, ctx, context, setting, scope_name, connective="is"
    ):
        """Show the value of the given setting in the given scope."""

        value = setting.get_value_in_scope(context, scope_name)
        clean_value = cleanup_value(value)
        embed = discord.Embed(
            title=f"{setting.name.title()} {connective} {clean_value} for this {scope_name}",
            description=setting.merge_values_help,
            colour=discord.Colour.blurple(),
        )

        await ctx.send(embed=embed)


def setup(bot):
    # All settings are made available on the bot instance for easy access
    bot.settings = {setting.name: setting(bot) for setting in ALL_SETTINGS}
    settings = bot.settings.values()

    bot.add_cog(Settings(bot, settings))
