import logging
import re
from datetime import datetime, timedelta

import emoji
import discord
from discord.ext import commands

from chatbot.models import Statement
from chatbot.response import get_response
from chatbot.pairs import get_pairs


# Set up logging
logger = logging.getLogger(__name__)


def is_command(text):
    """Check if the given text appears to be a command."""

    if text.startswith('pls '):
        return True

    return re.match(r'^\w{0,3}[^0-9a-zA-Z\s\'](?=\w)', text) is not None


class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, msg):
        """Process a message and send a chatbot response to the channel."""

        logger.info('Receved message "%s"', msg.clean_content)
        if self.should_ignore(msg): return

        if self.should_respond(msg):
            async with msg.channel.typing():
                # Get a response from the chatbot
                logger.info('Getting response')

                session = self.bot.Session()
                response, confidence = get_response(msg.content, session)
                session.close()

            if confidence > 0.5:
                # Send to Discord
                logger.info(
                    'Sending response "%s" with confidence %d',
                    response, confidence
                )
                await msg.channel.send(response)
            else:
                # Uncertain, don't respond
                logger.info('Confidence %d, not sending anything', confidence)
        else:
            logger.info('Not a DM, not responding')

        if self.should_learn(msg):
            # Look for a previous message
            previous_msg = await self.get_previous(msg)
            if previous_msg is not None:
                # Learn this statement
                logger.info(
                    'Learning "%s" as a response to "%s"',
                    msg.clean_content, previous_msg.clean_content
                )

                session = self.bot.Session()
                session.add(Statement(
                    text=msg.content,
                    responding_to=previous_msg.content,
                    responding_to_bigram=' '.join(
                        get_pairs(previous_msg.content)
                    )
                ))
                session.commit()
                session.close()

    def should_ignore(self, msg):
        """Check if the given message should be completely ignored."""

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

    def should_respond(self, msg):
        """Check if the given message should be responded to."""

        return msg.channel.type == discord.ChannelType.private

    def should_learn(self, msg):
        """Check if the given message should be learned from."""

        # Check channel names for bad strings
        if msg.channel.type == discord.ChannelType.text:
            if 'spam' in msg.channel.name:
                logger.info('Channel name contains "spam", not learning')
                return False
            if 'command' in msg.channel.name: # Will also catch "commands"
                logger.info('Channel name contains "command", not learning')
                return False
            if 'meme' in msg.channel.name:
                logger.info('Channel name contains "meme", not learning')
                return False

        return True

    async def get_previous(self, msg, minutes=5):
        """
        Get the previous message to store in database.

        Find a message in the same channel as the one given, which is directly
        before and occured within X minutes. Return the text of this message
        if it is found, otherwise return None.
        """

        logger.info('Looking for a previous message')

        prev = await msg.channel.history(
            # Find the message directly before this
            limit=1,
            oldest_first=False,
            before=msg,
            # Limit to messages within timeframe
            after=msg.created_at - timedelta(minutes=minutes)
        ).flatten()

        if len(prev) > 0:
            # We found a previous message
            prev_msg = prev[0]

            if prev_msg.author == msg.author:
                logger.info('Found message has same author, not returning')
                return

            if prev_msg.author.bot and prev_msg.author != self.bot.user:
                logger.info(
                    'Found message is from a bot other than '
                    'ourself, not returning'
                )
                return

            if len(prev_msg.content) == 0:
                logger.info('Found message has no text, not returning')
                return

            # This message is valid!
            logger.info('Found "%s"', prev_msg.clean_content)
            return  prev_msg
        else:
            # We didn't find any messages
            logger.info('No message found')


def setup(bot):
    bot.add_cog(Chat(bot))
