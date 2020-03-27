import asyncio
import concurrent.futures
import logging
import re
from datetime import datetime, timedelta

import emoji
import discord
from discord.ext import commands
from chatterbot.conversation import Statement

from caps import capitalize


# Set up logging
logger = logging.getLogger(__name__)

# Run Chatterbot in threads
chatterbot_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)


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

        # Build query statement
        statement = await self.query_statement(msg)

        if self.should_respond(msg):
            # Get a chatbot response
            async with msg.channel.typing():
                logger.info('Getting response')

                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    chatterbot_executor,
                    lambda: self.bot.chatter.get_response(statement)
                )

            # Send to Discord
            await self.send_response(response, msg)
        else:
            logger.info('Not a DM, not responding')

        if (statement.in_response_to is not None) and self.should_learn(msg):
            # Learn from the statement
            self.bot.chatter.learn_response(
                statement,
                statement.in_response_to
            )

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Learn unicode emoji reactions as responses."""

        logger.info(
            'Received reaction on "%s"',
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

                # Learn the emoji as a response
                self.bot.chatter.learn_response(
                    statement,
                    statement.in_response_to
                )

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

    async def send_response(self, response, msg):
        """
        Send the response to the given channel.

        :param response: Statement object to send
        :param msg: Message we are responding to
        """

        if response.confidence < 0.5:
            # Do not send unconfident response
            logger.info('Unconfident, not sending anything')
            return

        logger.info('Sending response to channel')

        # Ensure response has correct capitalization
        form_text = capitalize(response.text)

        # Attempt to send emojis as a reaction
        if form_text in emoji.UNICODE_EMOJI:
            try:
                await msg.add_reaction(form_text)
            except discord.Forbidden:
                pass # Continue to send as message
            else:
                return # Reaction added successfully

        # Just send raw message
        await msg.channel.send(form_text)

    def conv_id(self, msg):
        """Get a conversation ID for the given message."""

        return f'channel-{msg.channel.id}'

    async def query_statement(self, msg):
        """Build a Statement from the user's message."""

        logger.info('Building query statement')

        # Get previous message
        prev = await self.get_previous(msg)

        statement = Statement(
            # Use message contents for statement text
            msg.clean_content,
            in_response_to=prev,
            # Use Discord IDs for conversation and person
            conversation=self.conv_id(msg),
            persona=msg.author.id,
        )

         # Make sure the statement has its search text saved
        statement.search_text = self.bot.chatter.storage.tagger \
            .get_bigram_pair_string(statement.text)
        # And for in_response_to
        if statement.in_response_to is not None:
            statement.search_in_response_to = self.bot.chatter.storage.tagger \
                .get_bigram_pair_string(statement.in_response_to)

        return statement

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
            return  prev_msg.clean_content
        else:
            # We didn't find any messages
            logger.info('No message found')


def setup(bot):
    bot.add_cog(Chat(bot))
