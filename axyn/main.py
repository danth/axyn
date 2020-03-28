from functools import wraps
import logging
import os.path

from discord.ext import commands
import chickennuggets
import sqlalchemy
import spacy

from datastore import get_path
from chatbot.models import Base


# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Set up Discord bot
logger.info('Setting up bot')
bot = commands.Bot(command_prefix='a!')


def launch():
    """Launch the Discord bot."""

    # Connect to database
    db_url = 'sqlite:///' + get_path('axyn.sqlite3')
    engine = sqlalchemy.create_engine(db_url)
    # Create tables
    Base.metadata.create_all(engine)
    # Create Session class
    bot.Session = sqlalchemy.orm.sessionmaker(bind=engine)

    # Load extensions
    logger.info('Loading extensions')
    chickennuggets.load(bot, ['help', 'errors'])
    bot.load_extension('chat')
    bot.load_extension('react')
    bot.load_extension('train')
    bot.load_extension('status')
    bot.load_extension('analyse')

    # Connect to Discord and start bot
    logger.info('Starting bot')
    bot.run(os.environ['DISCORD_TOKEN'])


if __name__ == '__main__':
    launch()
