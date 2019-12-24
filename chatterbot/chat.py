import logging
from datetime import timedelta

from discord.ext import commands
from chatterbot.conversation import Statement


# Set up logging
logger = logging.getLogger(__name__)


class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, msg):
        """
        Process a message and send a chatbot response to the channel.

        If the bot doesn't understand, no message will be sent.
        """

        logger.info('Received message "%s"', msg.clean_content)
        if msg.author.bot:
            logger.info('Author is a bot, ignoring')
            return

        # Trigger a typing indicator while chatterbot processes
        await msg.channel.trigger_typing()

        # Build query statement
        statement = await self.query_statement(msg)

        # Get a response
        logger.info('Getting response')
        response = self.bot.chatter.get_response(statement)

        # Send response to channel
        if response.text == '':
            logger.info('Bot did not understand, not sending anything.')
        else:
            logger.info('Sending response to channel')
            await msg.channel.send(response.text)

    async def query_statement(self, msg):
        """Build a Statement from the user's message."""

        logger.info('Building query statement')

        # Get previous message
        prev = await self.get_previous(msg)

        return Statement(
            # Use message contents for statement text
            msg.clean_content,
            in_response_to=prev,
            # Use Discord IDs for conversation and person
            conversation=msg.channel.id,
            persona=msg.author.id,
        )

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
            before=msg,
            # Limit to messages within timeframe
            after=msg.created_at - timedelta(minutes=minutes)
        ).flatten()

        if len(prev) > 0:
            # We found a previous message
            logger.info('Found "%s"', prev[0].clean_content)
            return  prev[0].clean_content
        else:
            # We didn't find any messages
            logger.info('No message found')


def setup(bot):
    bot.add_cog(Chat(bot))
