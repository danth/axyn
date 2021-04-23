import re

import discord


def _is_command(text):
    """Check if the given text appears to be a command."""

    if text.startswith("pls "):
        return True

    return re.match(r"^\w{0,3}[^0-9a-zA-Z\s\'](?=\w)", text) is not None


def _reason_to_ignore(bot, message, allow_axyn=False):
    """If the given message should be ignored, return a reason why."""

    if message.type != discord.MessageType.default:
        return "this is not a regular message"

    if len(message.content) == 0:
        return "this message has no text"

    if message.author == bot.user:
        if not allow_axyn:
            return "this message is authored by Axyn"
    elif message.author.bot:
        return "this message is authored by a bot"

    if message.content.startswith("a!"):
        return "this message is an Axyn command"

    if (
        # In DMs, only Axyn commands will be used
        message.channel.type != discord.ChannelType.private
        and _is_command(message.content)
    ):
        return "this message looks like a bot command"


def reason_not_to_reply(bot, message):
    """If the given message shouldn't be replied to, return a reason why."""

    return _reason_to_ignore(bot, message)


def reason_not_to_react(bot, message):
    """If the given message shouldn't be reacted to, return a reason why."""

    return _reason_to_ignore(bot, message)


def reason_not_to_learn(bot, message):
    """If the given message shouldn't be learned, return a reason why."""

    # Only for text channels, not DMs
    if message.channel.type == discord.ChannelType.text:
        for bad_string in ["spam", "command", "meme"]:
            if bad_string in message.channel.name:
                return "the channel name contains " + bad_string

    return _reason_to_ignore(bot, message)


def reason_not_to_learn_pair(bot, previous_message, message):
    """If the given pair shouldn't be learned, return a reason why."""

    if previous_message.author == message.author:
        return "the previous message has the same author as this message"

    return _reason_to_ignore(bot, previous_message, allow_axyn=True)


def reason_not_to_learn_reaction_pair(bot, reaction, reaction_user):
    """If the given reaction pair shouldn't be learned, return a reason why."""

    if not isinstance(reaction.emoji, str):
        return "this is not a unicode emoji"

    if reaction_user.bot:
        return "this reaction is from a bot"

    if reaction_user == reaction.message.author:
        return "this reaction is from the message author"

    return _reason_to_ignore(bot, reaction.message, allow_axyn=True)