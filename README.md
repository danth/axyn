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

### Chat

You can chat to Axyn at any time by sending it a DM. It will display the typing
status while a response is generated. If the bot stops typing and nothing is
sent, this means that it didn't know how to respond or was less than 50%
certain.

![Screenshot of example conversation](images/Screenshot_20200426_124703.png)

Axyn will also respond to messages in servers, if noone else has responded
within 3 minutes and it is more than 80% certain. Mention the bot to get an
instant response.

### Reactions

Axyn adds reactions to messages it receives, both in servers and DMs, if it has
learned any which match that message.

## How does it work?

See the 'how it works' section of [Flipgenic](https://github.com/danth/flipgenic/blob/master/README.md#how-does-it-work).
Axyn is simply a Discord wrapper around this library (although, Flipgenic was
originally `axyn.chatbot` before it was extracted).
