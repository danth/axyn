<p align="center">
  <img
    src="images/axyn.png"
    alt="Axyn logo"
  />
</p>

# Axyn

A Discord chatbot built using Flipgenic.

## Run

Obtain a bot token from the
[Discord developer portal](https://discord.com/developers/applications).
Currently, the server members intent is required.

### Without Docker

```sh
python -m pip install -e .
python -m spacy download en_core_web_md
DISCORD_TOKEN=… axyn
```

### With Docker

```sh
docker build -t axyn .
docker container create -e DISCORD_TOKEN=… --mount source=axyn,target=/axyn --name axyn axyn
docker start -a axyn
```

## Usage

### Required Permissions

- Manage slash commands
- Send messages
- Embed links
- Read message history
- Add reactions

### Chat

Axyn will reply immediately if you:

- Send it a direct message
- Mention it
- Reply to a message it sent
- Talk in a channel with `axyn` in its name

Otherwise, it will wait some time before replying. The delay is adjusted using
the average interval between messages in the current channel.

![Screenshot of example conversation](images/Screenshot_20200426_124703.png)

If the bot stops typing and nothing is sent, it was unsure how to respond.
More uncertain messages are allowed through when replying immediately.

Axyn will learn a message if it fits all of these criteria:

- It contains some text
- It does not look like a bot command
- It was sent by a human user
- The channel does not have `spam`, `command` or `meme` in its name
- The learning setting is enabled
- It is a reply, or Axyn can find a message which:
  - Contains some text
  - Is directly above this message
  - Was sent by Axyn or a human user (not other bots)
  - Was sent by a different author to this message
  - Was sent no more than 5 minutes before this message

### Reactions

Axyn adds reactions to incoming messages if it has learned any which match that
message.

Axyn will learn a reaction if it fits all of these criteria:

- It was added by a human user
- It was not added by the author of the message being reacted to
- The learning setting is enabled
- The message being reacted to contains some text
- The message being reacted to does not look like a bot command
- The message being reacted to was sent by Axyn or a human user (not other bots)

### Settings

Axyn has some settings which can be edited using traditional commands.
You may obtain a list of the available settings by sending `a!help`.

Each setting is stored for the current user, channel and/or server. Typing a
setting's main command will display its current value in each of these scopes,
with a description of how the scopes have been combined to produce a final
value. To change a setting you should type its command, followed by the scope
you want to change, followed by the new choice.

## How does it work?

See the 'how it works' section of [Flipgenic](https://github.com/danth/flipgenic/blob/master/README.md#how-does-it-work).
Axyn is simply a Discord wrapper around this library (although, Flipgenic was
originally `axyn.chatbot` before it was extracted).
