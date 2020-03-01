import logging
import os.path

from discord.ext import commands
from chatterbot import ChatBot, trainers
from chatterbot.response_selection import get_most_frequent_response
import chickennuggets

from datastore import get_path


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Discord bot
logger.info('Setting up bot')
bot = commands.Bot(command_prefix='a!')


# Find database
db_file =  get_path('database.sqlite3')
logger.info('Database at %s', db_file)

do_train = not os.path.exists(db_file)
if do_train:
    logger.info('Database does not yet exist, running initial trainers')

# Set up Chatterbot
bot.chatter = ChatBot(
    'Axyn',
    # Store data in SQLite
    storage_adapter='chatterbot.storage.SQLStorageAdapter',
    database_uri=f'sqlite:///{db_file}',
    logic_adapters=[
        # Allow math questions such as "What is 5 squared?"
        'chatterbot.logic.MathematicalEvaluation',
        # Allow asking for the current time
        {
            'import_path': 'chatterbot.logic.TimeLogicAdapter',
            'negative': [
                'it is time to go to sleep',
                'what is your favorite color',
                'i had a great time',
                'thyme is my favorite herb',
                'do you have time to look at my essay',
                'how do you have the time to do all this',
                'what is it',
                'hello',
                'thank you',
                'how are you?'
            ]
        },
        # General responses learned in database
        {
            'import_path': 'chatterbot.logic.BestMatch',
            'maximum_similarity_threshold': 0.90
        }
    ],
    response_selection_method=get_most_frequent_response,
    # Disable default learning as we will only store select statements
    read_only=True,
)

if do_train:
    # Do initial training
    logger.info('Training chatterbot')

    # Simple list
    trainer = trainers.ListTrainer(bot.chatter)
    trainer.train([
        'Hello',
        'Hi!',
        'How are you?',
        'Fine, what about you?',
        'I\'m fine, thanks!',
    ])

    # Chatterbot Corpus
    cc_trainer = trainers.ChatterBotCorpusTrainer(bot.chatter)
    cc_trainer.train('chatterbot.corpus')

    # Ubuntu Corpus, only if configured in environment variable
    if os.environ.get('TRAIN_UBUNTU', False):
        uc_trainer =  trainers.UbuntuCorpusTrainer(bot.chatter)
        uc_trainer.train()


def launch():
    """Launch the Discord bot."""

    # Load extensions
    logger.info('Loading extensions')
    chickennuggets.load(bot, ['help', 'errors'])
    bot.load_extension('chat')
    bot.load_extension('train')
    bot.load_extension('status')
    bot.load_extension('analyse')

    # Connect to Discord and start bot
    logger.info('Starting bot')
    bot.run(os.environ['DISCORD_TOKEN'])


if __name__ == '__main__':
    launch()
