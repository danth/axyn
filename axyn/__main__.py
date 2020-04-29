import logging
import os.path
from functools import wraps

import chickennuggets
import spacy
import sqlalchemy
from axyn.datastore import get_path
from discord.ext import commands
from axyn.models import Base

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def launch():
    """Launch the Discord bot."""
    # Set up Discord bot
    logger.info("Setting up bot")
    bot = commands.Bot(command_prefix="a!")

    # Connect to database
    db_url = "sqlite:///" + get_path("axyn.sqlite3")
    engine = sqlalchemy.create_engine(db_url)
    # Create tables
    Base.metadata.create_all(engine)
    # Create Session class
    bot.Session = sqlalchemy.orm.sessionmaker(bind=engine)

    # Load extensions
    logger.info("Loading extensions")
    chickennuggets.load(bot, ["help", "errors"])
    bot.load_extension("axyn.chat")
    bot.load_extension("axyn.react")
    bot.load_extension("axyn.train")
    bot.load_extension("axyn.status")
    bot.load_extension("axyn.analyse")

    # Connect to Discord and start bot
    logger.info("Starting bot")
    bot.run(os.environ["DISCORD_TOKEN"])


if __name__ == "__main__":
    launch()
