import logging
import os.path

import discord
import discordhealthcheck
import spacy
import sqlalchemy
from flipgenic import Responder

from axyn.datastore import get_path
from axyn.handle import setup_handlers
from axyn.consent import setup_consent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def launch():
    logger.info("Setting up client")
    intents = discord.Intents.default()
    intents.members = True  # Required for on_reaction_add in DMs
    client = discord.Client(intents=intents)

    logger.info("Loading NLP model")
    # Create model here so Flipgenic does not load it twice
    model = spacy.load("en_core_web_md", disable=["ner", "textcat"])

    logger.info("Initializing message responder")
    client.message_responder = Responder(get_path("messages"), model)
    logger.info("Initializing reaction responder")
    client.reaction_responder = Responder(get_path("reactions"), model)

    logger.info("Attaching handlers")
    setup_handlers(client)
    setup_consent(client)
    discordhealthcheck.start(client)

    logger.info("Starting client")
    client.run(os.environ["DISCORD_TOKEN"])


if __name__ == "__main__":
    launch()
