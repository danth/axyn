<p align="center">
  <img
    src="images/axyn.png"
    alt="Axyn logo"
  />
</p>

# Axyn

A chatbot using rudimentary algorithms.

![Screenshot of an example conversation](images/Screenshot_20200426_124703.png)

## Instructions for users

### Teaching Axyn

Everything Axyn can say is a quote from a conversation it's seen in the past.
As you have real conversations, it will pick up on phrases you use, and
eventually repeat them back to you.

For Axyn to turn a message into a quote, it needs to match it up with a
previous message. This is so it has some context to know when the quote is
relevant. Using the reply button helps to make this more accurate, especially
in busy channels.

### Getting a reply

Axyn will occasionally join in with real conversations. The chance of this
happening increases as Axyn learns more, but decreases when there are more
people in the chat.

If you seem to be talking to Axyn directly, then it is guaranteed to respond.
There are a few things you can do to trigger this:

- Pinging it
- Hitting reply on one of its messages
- Sending it a direct message
- Sending a message in a channel called `#axyn`

### Maintaining privacy

Axyn will only quote you if you give it permission to do so. You can do this by
typing `/consent` and making a choice from the menu. Alternatively, if it's
able, Axyn will invite you to consent the first time you interact with it.

Your consent choice applies retrospectively, so after you accept, Axyn may
collect historic messages from channels it can see. Similarly, removing consent
will erase all messages that were previously collected.

To avoid leaking private information, it is strongly recommended to choose the
middle option. This means your messages can only be shared if everyone who
would see the quote can already see the original. For example, messages from
a group chat with you and a friend could be used in Axyn's direct messages to
that friend, but they could not be used in a larger server.

The top option requires extreme caution because it effectively makes all of
your messages public. However, it can be useful if you want to port quotes
between different groups of friends, or feed Axyn lines in direct messages and
have them spontaneously appear.

## Instructions for channel owners

Axyn needs the following permissions to work fully:

- Send messages
- Embed links
- Manage slash commands

You should remove its permission to send messages in important channels, such
as those for announcements.

You should also ensure Axyn is not given permission to ping everyone.

## Instructions for the bot owner

Obtain a bot token from the
[Discord developer portal](https://discord.com/developers/applications).
Access to server members and message content must both be enabled.

Then, run the following commands, inserting your bot token as shown.

```sh
python -m pip install -e .
DISCORD_TOKEN=… python -m axyn
```

