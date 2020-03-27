import asyncio
import concurrent.futures
import logging
import re

import discord
from discord.ext import commands
from chatterbot.conversation import Statement


# Set up logging
logger = logging.getLogger(__name__)

# Run Chatterbot in threads
chatterbot_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)


def is_command(text):
    """Check if the given text appears to be a command."""

    if text.startswith('pls '):
        return True

    return re.match(r'^\w{0,3}[^0-9a-zA-Z\s\'](?=\w)', text) is not None


class React(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, msg):
        """Process a message and react if possible."""

        # Get a chatbot response
        if not self.should_ignore(msg):
            logger.info('Getting reaction')

            # Build query statement
            statement = self.query_statement(msg)

            loop = asyncio.get_event_loop()
            reaction = await loop.run_in_executor(
                chatterbot_executor,
                lambda: self.bot.reactor.get_response(statement)
            )

            # Add reaction
            if reaction.confidence >= 0.5:
                logger.info('Reacting with %s', reaction.text)
                await msg.add_reaction(reaction.text)
            else:
                logger.info('Reaction unconfident, not reacting with anything')

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Learn unicode emoji reactions as responses."""

        logger.info(
            'Received reaction %s on "%s"',
            reaction.emoji,
            reaction.message.clean_content
        )

        # Use original message for ignore checking
        if self.should_learn_reaction(reaction.message, user):
            # Check if this is a unicode emoji or a custom one
            if type(reaction.emoji) == str:
                # Build a Statement
                statement = Statement(
                    text=reaction.emoji,
                    in_response_to=reaction.message.clean_content,
                    conversation=self.conv_id(reaction.message),
                    persona=user.id,
                )
                # Save search text for in_response_to
                statement.search_in_response_to = self.bot.reactor.storage.tagger \
                    .get_bigram_pair_string(statement.in_response_to)
                # We don't need to do it for the text because it is an emoji
                # and wouldn't be tagged

                # Learn the emoji as a response
                self.bot.reactor.learn_response(
                    statement,
                    statement.in_response_to
                )

    def should_ignore(self, msg):
        """Check if the given message should not be reacted to."""

        # Check if the author is a bot / system message
        if msg.author.bot or msg.type != discord.MessageType.default:
            logger.info('Author is a bot, ignoring')
            return True

        if len(msg.content) == 0:
            logger.info('Message has no text, ignoring')
            return True

        if is_command(msg.content):
            logger.info('Message appears to be a bot command, ignoring')
            return True

        return False

    def should_learn_reaction(self, msg, reaction_user):
        """Check if a reaction on the given message should be learned."""

        if reaction_user.bot:
            logger.info('Reaction is from a bot, not learning it')
            return False

        if reaction_user == msg.author:
            logger.info('Reaction is from message author, not learning it')
            return False

        if msg.author.bot and msg.author != self.bot.user:
            logger.info('Message is from foreign bot, not learning reaction')
            return False

        if len(msg.content) == 0:
            logger.info('Message has no text, not learning reaction')
            return False

        if is_command(msg.content):
            logger.info(
                'Message appears to be a bot command, not learning reaction')
            return False

        return True

    def conv_id(self, msg):
        """Get a conversation ID for the given message."""

        return f'channel-{msg.channel.id}'

    def query_statement(self, msg):
        """
        Build a Statement from the user's message.

        Compared to the statements used for chats, these contain less
        information to improve performance.
        """

        logger.info('Building reaction query statement')

        statement = Statement(
            # Use message contents for statement text
            msg.clean_content,
            # Use Discord IDs for conversation and person
            conversation=self.conv_id(msg),
            persona=msg.author.id,
        )

         # Make sure the statement has its search text saved
        statement.search_text = self.bot.reactor.storage.tagger \
            .get_bigram_pair_string(statement.text)

        return statement


def setup(bot):
    bot.add_cog(React(bot))
