from abc import ABC, abstractmethod

import discord
from discord.ext import commands
from sqlalchemy import BigInteger, Column

from axyn.models import Base
from axyn.settings.context import SettingContext


class Scope(ABC):
    @property
    @abstractmethod
    def name(self):
        """The name of this scope."""

    @abstractmethod
    def is_applicable(self, context):
        """Given a SettingContext, return whether this scope is applicable."""

    @abstractmethod
    def get_id(self, context):
        """Given a SettingContext, return the ID of the scope it is in."""

    @abstractmethod
    async def permission_check(self, ctx):
        """Check whether a user is allowed to edit this scope."""

    def __init__(self, bot, setting):
        self.bot = bot
        self.setting = setting

        # This dynamically defines a class with the given name
        self.model = type(
            f"{self.setting.name}_{self.name}_setting",
            (Base,),
            {
                "__tablename__": f"{self.setting.name}_{self.name}_setting",
                "id": Column(BigInteger, primary_key=True),
                "value": Column(self.setting.sql_datatype),
            },
        )

    async def check(self, ctx):
        """Return whether the command for this scope can be used in the given context."""

        applicable = self.is_applicable(SettingContext.from_context(ctx))
        if not applicable:
            return False

        return await self.permission_check(ctx)

    def get_value(self, context):
        """Fetch and return a value for the given context, or None if unset."""

        id_ = self.get_id(context)
        return self._get_database_value(id_)

    def set_value(self, context, value):
        """Set the value for the given context."""

        id_ = self.get_id(context)
        return self._set_database_value(id_, value)

    def _get_database_value(self, id_):
        """Fetch and return a value from the database, or None if not found."""

        session = self.bot.Session()
        entry = session.query(self.model).where(self.model.id == id_).one_or_none()
        session.close()

        if entry:
            return entry.value

    def _set_database_value(self, id_, value):
        """Upsert a value in the database."""

        session = self.bot.Session()
        session.merge(self.model(id=id_, value=value))
        session.commit()
        session.close()


class UserScope(Scope):
    name = "user"

    def is_applicable(self, context):
        return context.user is not None

    def get_id(self, context):
        return context.user.id

    async def permission_check(self, ctx):
        # Users can edit their own preference anywhere
        return True


class ChannelScope(Scope):
    name = "channel"

    def is_applicable(self, context):
        if context.channel:
            # Not applicable to DM channels
            return context.channel.type != discord.ChannelType.private

        return False

    def get_id(self, context):
        return context.channel.id

    async def permission_check(self, ctx):
        return await commands.has_permissions(administrator=True).predicate(ctx)


class GuildScope(Scope):
    name = "server"

    def is_applicable(self, context):
        return context.guild is not None

    def get_id(self, context):
        return context.guild.id

    async def permission_check(self, ctx):
        return await commands.has_permissions(administrator=True).predicate(ctx)


USER_SCOPES = [UserScope]
GUILD_SCOPES = [ChannelScope, GuildScope]
ALL_SCOPES = USER_SCOPES + GUILD_SCOPES
