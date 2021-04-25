from abc import ABC, abstractmethod

from sqlalchemy import BigInteger, Column
from axyn.models import Base


class Scope(ABC):
    @property
    @abstractmethod
    def name(self):
        """The name of this scope."""

    @abstractmethod
    def get_id(self, ctx):
        """Given a context, get the current scope and return its ID."""

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

    def get_value(self, ctx):
        """Fetch and return a value for the given context, or None if unset."""

        id_ = self.get_id(ctx)
        return self._get_database_value(id_)

    def set_value(self, ctx, value):
        """Set the value for the given context."""

        id_ = self.get_id(ctx)
        return self._set_database_value(id_, value)

    def _get_database_value(self, id_):
        """Fetch and return a value from the database, or None if not found."""

        session = self.bot.Session()
        entry = (
            session
            .query(self.model)
            .where(self.model.id == id_)
            .one_or_none()
        )
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

    def get_id(self, ctx):
        return ctx.author.id


class ChannelScope(Scope):
    name = "channel"

    def get_id(self, ctx):
        return ctx.channel.id


class GuildScope(Scope):
    name = "server"

    def get_id(self, ctx):
        return ctx.guild.id


USER_SCOPES = [UserScope]
GUILD_SCOPES = [ChannelScope, GuildScope]
ALL_SCOPES = USER_SCOPES + GUILD_SCOPES
