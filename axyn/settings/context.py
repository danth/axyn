class SettingContext:
    """Similar to discord.Context, but can be constructed outside of commands."""

    def __init__(self, user, channel, guild):
        self.user = user
        self.channel = channel
        self.guild = guild

    @classmethod
    def from_message(cls, message):
        """Construct using data from the given message."""

        return cls(message.author, message.channel, message.guild)

    @classmethod
    def from_context(cls, ctx):
        """Construct using data from the given discord.Context."""

        return cls(ctx.author, ctx.channel, ctx.guild)
