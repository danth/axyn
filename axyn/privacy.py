import discord


def _members_to_set(members):
    """
    Convert a list of members to a set of their IDs.

    Bot users are filtered out.
    """

    return set(member.id for member in members if not member.bot)


def _channel_members(channel):
    """List everyone who can view a channel."""

    if isinstance(channel, discord.DMChannel):
        return [channel.recipient]

    if isinstance(channel, discord.GroupChannel):
        return channel.recipients

    return channel.members


def should_send_in_channel(client, message, current_channel):
    """
    Return whether a message should be sent to a channel.

    This is only true if everyone who can view the current channel can also
    view the channel where the message was originally sent.
    """

    original_channel = client.get_channel(int(message.metadata))

    if current_channel == original_channel:
        return True

    # All members of the current channel must be members of the original channel
    original_channel_members = _members_to_set(_channel_members(original_channel))
    current_channel_members = _members_to_set(_channel_members(current_channel))
    return current_channel_members.issubset(original_channel_members)


def filter_responses(client, messages, current_channel):
    """Remove any messages from the given list which are not allowed to be sent."""

    return [
        message for message in messages
        if should_send_in_channel(client, message, current_channel)
    ]
