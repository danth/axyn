import re

import discord


def is_command(text):
    """Check if the given text appears to be a command."""

    if text.startswith("pls "):
        return True

    return re.match(r"^\w{0,3}[^0-9a-zA-Z\s\'](?=\w)", text) is not None


def _reason_to_ignore(client, message, allow_axyn=False):
    """If the given message should be ignored, return a reason why."""

    if (
        message.type != discord.MessageType.default and
        message.type != discord.MessageType.reply
    ):
        return "this is not a regular message"

    if len(message.content) == 0:
        return "this message has no text"

    if message.author == client.user:
        if not allow_axyn:
            return "this message is authored by Axyn"
    elif message.author.bot:
        return "this message is authored by a bot"

    if message.channel.type != discord.ChannelType.private and is_command(
        message.content
    ):
        return "this message looks like a bot command"


def reason_not_to_reply(client, message):
    """If the given message shouldn't be replied to, return a reason why."""

    return _reason_to_ignore(client, message)


def reason_to_ignore_interval(client, previous_message, message):
    """If the given pair's interval should be ignored, return a reason why."""

    if previous_message.author == message.author:
        return "both messages have the same author"

    return _reason_to_ignore(client, message) or _reason_to_ignore(
        client, previous_message, allow_axyn=True
    )


def is_direct(client, message):
    """Return whether the given message is directly talking to Axyn."""

    return (
        message.channel.type == discord.ChannelType.private
        or client.user.mentioned_in(message)
        or (
            message.reference
            and message.reference.resolved
            and message.reference.resolved.author == client.user
        )
        or "axyn" in message.channel.name
    )

