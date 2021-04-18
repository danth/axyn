import asyncio
import logging
import re
from datetime import datetime, timedelta

import discord
import emoji
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

        # Remove task for previous message, if any
        if msg.channel.id in self.response_timers:
            self.response_timers[msg.channel.id].cancel()

        # Spawn a new task to reply to this message
        self.response_timers[msg.channel.id] = asyncio.create_task(
            self.schedule_process_response(msg)
        )

        if self.should_learn(msg):
            await self.learn(msg)

    def preprocess_message(self, msg):
        content = msg.clean_content

        # Strip off leading @Axyn if it exists
        axyn = f"@{self.bot.user.display_name}"
        if content.startswith(axyn):
            content = content[len(axyn) :]

        # Remove leading/trailing whitespace
        return content.strip()

    def get_response(self, msg):
        logger.info('Getting response to "%s"', msg.clean_content)

        content = self.preprocess_message(msg)
        logger.info('Preprocessed to "%s"', content)

        return self.bot.message_responder.get_response(content)

    def is_direct(self, msg):
        """Return whether the given message is directly talking to Axyn."""

        return (
            msg.channel.type == discord.ChannelType.private
            or self.bot.user.mentioned_in(msg)
        )

    def get_reply_delay(self, msg):
        """Return number of seconds to wait before replying to the given message."""

        if self.is_direct(msg):
            return 0
        else:
            return 180

    def get_distance_threshold(self, msg):
        """Return the maximum acceptible distance for replies to the given message."""

        if self.is_direct(msg):
            return 4
        else:
            return 1.5

    async def schedule_process_response(self, msg):
        """Respond to the given message after a suitable (possibly 0) delay."""

        await asyncio.sleep(self.get_reply_delay(msg))
        await self.process_response(msg)

    async def process_response(self, msg):
        """Respond to the given message."""

        # Get a response from the chatbot
        async with msg.channel.typing():
            response, distance = self.get_response(msg)

        acceptable_distance = self.get_distance_threshold(msg)
        if distance <= acceptable_distance:
            # Send to Discord
            logger.info(
                'Responding to "%s" with "%s" at distance %.2f',
                msg.clean_content,
                response,
                distance,
            )
            await msg.channel.send(response)
        else:
            # Uncertain, don't respond
            logger.info(
                'Distance %.2f > %.2f, not responding to "%s"',
                distance,
                acceptable_distance,
                msg.clean_content,
            )

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

    async def learn(self, msg):
        """Learn from the given message."""

        # Look for a previous message
        previous_msg = await self.get_previous(msg)
        if not previous_msg:
            return

        # Preprocess both messages
        content = self.preprocess_message(msg)
        previous_content = self.preprocess_message(previous_msg)

        # Learn this statement
        logger.info('Learning "%s" as a response to "%s"', content, previous_content)
        self.bot.message_responder.learn_response(previous_content, content)

    async def get_previous(self, msg, minutes=5):
        """
        Get the previous message to store in database.

        Find a message in the same channel as the one given, which is directly
        before and occured within X minutes. Return the text of this message
        if it is found, otherwise return None.
        """

        logger.info("Looking for a previous message")

        if msg.reference and msg.reference.resolved:
            logger.info(
                'Found "%s" as a reference',
                msg.reference.resolved.clean_content,
            )
            return msg.reference.resolved

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
            logger.info('Found "%s" as the previous message', prev_msg.clean_content)
            return prev_msg
        else:
            # We didn't find any messages
            logger.info("No message found")


def setup(bot):
    bot.add_cog(Chat(bot))
