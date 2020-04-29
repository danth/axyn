import asyncio
import logging
import re
from datetime import datetime, timedelta

import discord
import emoji
from axyn.chatbot.response import get_response
from axyn.chatbot.train import train_statement
from discord.ext import commands

# Set up logging
logger = logging.getLogger(__name__)


def is_command(text):
    """Check if the given text appears to be a command."""

    if text.startswith("pls "):
        return True

    return re.match(r"^\w{0,3}[^0-9a-zA-Z\s\'](?=\w)", text) is not None


class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.response_timers = dict()

    @commands.Cog.listener()
    async def on_message(self, msg):
        """Process a message and send a chatbot response to the channel."""

        logger.info('Receved message "%s"', msg.clean_content)
        if self.should_ignore(msg):
            return

        if msg.channel.type == discord.ChannelType.private:
            # Respond immediately to DMs
            await self.process_dm_response(msg)

        elif msg.channel.type == discord.ChannelType.text:
            # Delayed response to server channels
            if msg.channel.id in self.response_timers:
                # Remove timer for previous message
                self.response_timers[msg.channel.id].cancel()

            if len(msg.content) < 10:
                # Don't respond to short texts like "ok" or "yes"
                # Or greetings targetted at server members
                logger.info("Not responding to short server message")
            else:
                # Respond after a delay if no humans have responded
                logger.info("Delaying response to server message")
                self.response_timers[msg.channel.id] = asyncio.create_task(
                    self.process_server_response_later(msg)
                )

        if self.should_learn(msg):
            # Look for a previous message
            previous_msg = await self.get_previous(msg)
            if previous_msg is not None:
                # Learn this statement
                logger.info(
                    'Learning "%s" as a response to "%s"',
                    msg.clean_content,
                    previous_msg.clean_content,
                )

                session = self.bot.Session()
                train_statement(msg.content, previous_msg.content, session)
                session.close()

    async def process_dm_response(self, msg):
        """Send a response to a DM."""

        async with msg.channel.typing():
            # Get a response from the chatbot
            logger.info("Getting response")

            session = self.bot.Session()
            response, confidence = get_response(msg.content, session)
            session.close()

        if confidence > 0.5:
            # Send to Discord
            logger.info(
                'Sending response "%s" with confidence %.2f', response, confidence
            )
            await msg.channel.send(response)
        else:
            # Uncertain, don't respond
            logger.info("Confidence %.2f <= 0.5, not sending anything", confidence)

    async def process_server_response_later(self, *args, **kwargs):
        """Call process_server_response after a delay."""

        await asyncio.sleep(180)
        await self.process_server_response(*args, **kwargs)

    async def process_server_response(self, msg):
        """Respond to a message from a server."""

        # Get a response from the chatbot
        logger.info(
            'Getting response to delayed server message "%s"', msg.clean_content
        )

        session = self.bot.Session()
        response, confidence = get_response(msg.content, session)
        session.close()

        if confidence > 0.8:  # Higher threshold than DMs
            # Send to Discord
            logger.info(
                'Sending response "%s" with confidence %.2f', response, confidence
            )
            await msg.channel.send(response)
        else:
            # Uncertain, don't respond
            logger.info("Confidence %.2f <= 0.8, not sending anything", confidence)

    def should_ignore(self, msg):
        """Check if the given message should be completely ignored."""

        # Check if the author is a bot / system message
        if msg.author.bot or msg.type != discord.MessageType.default:
            logger.info("Author is a bot, ignoring")
            return True

        if len(msg.content) == 0:
            logger.info("Message has no text, ignoring")
            return True

        if msg.content.startswith("a!"):
            logger.info("Message is an Axyn command, ignoring")
            return True
        if (
            # In DMs, only Axyn commands will be used
            msg.channel.type != discord.ChannelType.private
            and is_command(msg.content)
        ):
            logger.info("Message appears to be a bot command, ignoring")
            return True

        return False

    def should_learn(self, msg):
        """Check if the given message should be learned from."""

        # Check channel names for bad strings
        if msg.channel.type == discord.ChannelType.text:
            if "spam" in msg.channel.name:
                logger.info('Channel name contains "spam", not learning')
                return False
            if "command" in msg.channel.name:  # Will also catch "commands"
                logger.info('Channel name contains "command", not learning')
                return False
            if "meme" in msg.channel.name:
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

        logger.info("Looking for a previous message")

        prev = await msg.channel.history(
            # Find the message directly before this
            limit=1,
            oldest_first=False,
            before=msg,
            # Limit to messages within timeframe
            after=msg.created_at - timedelta(minutes=minutes),
        ).flatten()

        if len(prev) > 0:
            # We found a previous message
            prev_msg = prev[0]

            if prev_msg.author == msg.author:
                logger.info("Found message has same author, not returning")
                return

            if prev_msg.author.bot and prev_msg.author != self.bot.user:
                logger.info(
                    "Found message is from a bot other than " "ourself, not returning"
                )
                return

            if len(prev_msg.content) == 0:
                logger.info("Found message has no text, not returning")
                return

            # This message is valid!
            logger.info('Found "%s"', prev_msg.clean_content)
            return prev_msg
        else:
            # We didn't find any messages
            logger.info("No message found")


def setup(bot):
    bot.add_cog(Chat(bot))
