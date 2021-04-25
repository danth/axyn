from abc import ABC, abstractmethod

from sqlalchemy import Boolean
from axyn.settings.scopes import ALL_SCOPES


class Setting(ABC):
    @property
    @abstractmethod
    def name(self):
        """The name of this setting."""

    @property
    @abstractmethod
    def thing(self):
        """
        A short description of what this setting controls.

        This should be formatted like "whether learning is enabled" or "how
        long Axyn waits before replying".
        """

    @property
    @abstractmethod
    def datatype(self):
        """The type of value this setting stores."""

    @property
    @abstractmethod
    def sql_datatype(self):
        """The type of value this setting stores, as an sqlalchemy column type."""

    @property
    @abstractmethod
    def available_scopes(self):
        """List of scopes this can be set for."""

    @abstractmethod
    def merge_values(self, **kwargs):
        """
        Merge values from different scopes into a single value.

        Values are passed as keyword arguments corresponding to the name of the
        scope, and will be None if they have not been set.
        """

    def __init__(self, bot):
        self.bot = bot

        self.scopes = [
            scope(self.bot, self)
            for scope in self.available_scopes
        ]

    def get_value(self, ctx):
        """Get the effective value of this setting in the given context."""

        values = self.get_all_values(ctx)
        return self.merge_values(**values)

    def get_value_in_scope(self, ctx, scope_name):
        """Get the value of this setting in the given context and scope."""

        return self.get_all_values(ctx)[scope_name]

    def get_all_values(self, ctx):
        """Get all values of this setting in the given context."""

        return {
            scope.name: scope.get_value(ctx)
            for scope in self.scopes
        }

    def set_value_in_scope(self, ctx, scope_name, value):
        """Set the value of this setting in the given context and scope."""

        for scope in self.scopes:
            if scope.name == scope_name:
                scope.set_value(ctx, value)
                break


class LearningSetting(Setting):
    name = "learning"
    thing = "whether Axyn will learn messages"
    datatype = bool
    sql_datatype = Boolean
    available_scopes = ALL_SCOPES

    def merge_values(self, user, channel, server):
        # If the channel or guild has explicitly disabled learning, honour that
        if channel is False or server is False:
            return False

        # Otherwise, use the user's preference
        return bool(user)


ALL_SETTINGS = [
    LearningSetting
]
