import logging
import os.path

import chickennuggets
import discord
import discordhealthcheck
import spacy
import sqlalchemy
from discord.ext import commands
from flipgenic import Responder

from axyn.datastore import get_path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def launch():
    """Launch the Discord bot."""
    # Set up Discord bot
    logger.info("Setting up bot")
    intents = discord.Intents.default()
    intents.members = True  # Required for on_reaction_add in DMs
    bot = commands.Bot(command_prefix="a!", intents=intents)

    # Create model here so Flipgenic does not load it twice
    logger.info("Loading NLP model")
    model = spacy.load("en_core_web_md", disable=["ner", "textcat"])

    logger.info("Initializing message responder")
    bot.message_responder = Responder(get_path("messages"), model)
    logger.info("Initializing reaction responder")
    bot.reaction_responder = Responder(get_path("reactions"), model)

    # Load extensions
    logger.info("Loading extensions")
    chickennuggets.load(bot, ["help", "errors"])
    bot.load_extension("axyn.handle")

    # Set up Docker health checks
    discordhealthcheck.start(bot)

    # Connect to Discord and start bot
    logger.info("Starting bot")
    bot.run(os.environ["DISCORD_TOKEN"])


if __name__ == "__main__":
    launch()
