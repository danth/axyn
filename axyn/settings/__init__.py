from abc import ABC, abstractmethod


def _get_database_value(model, thing, bot):
    """Fetch and return a value from the database, or None if not found."""

    session = bot.Session()
    entry = session.query(model).where(model.id == thing.id).one_or_none()
    session.close()

    if entry:
        return entry.value


def _set_database_value(model, thing, value, bot):
    """Update or add a value to the database."""

    session = bot.Session()
    session.merge(model(id=thing.id, value=value))
    session.commit()
    session.close()


class Setting(ABC):
    def __init__(self, bot):
        self.bot = bot

    @property
    @abstractmethod
    def name(self):
        """The name of this setting."""

    @property
    @abstractmethod
    def datatype(self):
        """The type of value this setting stores."""

    @property
    @abstractmethod
    def thing(self):
        """
        A short description of what this setting controls.

        This should be formatted like "whether learning is enabled" or "how
        long Axyn waits before replying".
        """

    @property
    def user_model(self):
        """
        The database model which stores user-level settings.

        Should have a BigInteger primary key named `id` and a column named
        `value`. If None, this setting is not available on the user level.
        """

    @property
    def channel_model(self):
        """
        The database model which stores channel-level settings.

        Should have a BigInteger primary key named `id` and a column named
        `value`. If None, this setting is not available on the channel level.
        """

    @property
    def guild_model(self):
        """
        The database model which stores guild-level settings.

        Should have a BigInteger primary key named `id` and a column named
        `value`. If None, this setting is not available on the guild level.
        """

    @abstractmethod
    def merge_values(self, user_value, channel_value, guild_value):
        """
        Merge values from different levels into a single value.

        Values will be None if they have not been set.
        Levels which do not have a database model will always be None.
        """

    def get_value(self, user, channel, guild):
        """Get the value of this setting in the given context."""

        return self.merge_values(
            self.get_user_value(user),
            self.get_channel_value(channel),
            self.get_guild_value(guild),
        )

    def get_user_value(self, user):
        """Get the value of this setting for the given user."""

        if self.user_model:
            return _get_database_value(self.user_model, user, self.bot)

    def get_channel_value(self, channel):
        """Get the value of this setting in the given channel."""

        if self.channel_model:
            return _get_database_value(self.channel_model, channel, self.bot)

    def get_guild_value(self, guild):
        """Get the value of this setting in the given guild."""

        if self.guild_model:
            return _get_database_value(self.guild_model, guild, self.bot)

    def set_user_value(self, user, value):
        """Set the value of this setting for the given user."""

        if not self.user_model:
            raise Exception("This setting can not be set for users.")

        _set_database_value(self.user_model, user, value, self.bot)

    def set_channel_value(self, channel, value):
        """Set the value of this setting in the given channel."""

        if not self.channel_model:
            raise Exception("This setting can not be set for channels.")

        _set_database_value(self.channel_model, channel, value, self.bot)

    def set_guild_value(self, guild, value):
        """Set the value of this setting in the given guild."""

        if not self.guild_model:
            raise Exception("This setting can not be set for guilds.")

        _set_database_value(self.guild_model, guild, value, self.bot)
