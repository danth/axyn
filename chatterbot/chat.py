import logging
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
from chatterbot.conversation import Statement


# Set up logging
logger = logging.getLogger(__name__)


class Summon:
    def __init__(self, channel, cmd, resp):
        """
        A summoning to a channel.

        :param channel: The channel the bot has been summoned to.
        :param cmd: The user's command message.
        :param resp: The "summoned" response to the command.
        """

        self.channel = channel
        self.cmd = cmd
        self.resp = resp

        self.last_activity = resp


class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.summons = dict()

        self.auto_unsummon.start()

    def cog_unload(self):
        self.auto_unsummon.cancel()

    @commands.command()
    async def summon(self, ctx):
        """Summon the bot to listen to this channel."""

        if self.summons.get(ctx.channel.id) is not None:
            # Bot was already summoned
            await ctx.send(embed=discord.Embed(
                description="I have already been summoned!",
                colour=discord.Colour.orange()
            ))
            return

        # Respond to the command
        resp = await ctx.send(embed=discord.Embed(
            title='Summon frame opened',
            description=(
                'I am now responding to messages in this channel.\n'
                'Use `c!unsummon` when you are finished talking.'
            ),
            colour=discord.Colour.green()
        ))

        # Store the summoning
        self.summons[ctx.channel.id] = Summon(
            ctx.channel,
            ctx.message,
            resp
        )

    @commands.command()
    async def unsummon(self, ctx):
        """Stop listening to this channel."""

        if self.summons.get(ctx.channel.id) is None:
            # Bot was never summoned
            await ctx.send(embed=discord.Embed(
                description="I was never summoned!",
                colour=discord.Colour.orange()
            ))
            return

        # Get conversation ID
        id = self.conv_id(ctx.message)

        # Unsummon
        self.summons[ctx.channel.id] = None

        # Respond to the command
        e = discord.Embed(
            title='Summon frame closed',
            description='I am no longer responding to messages in this channel.',
            colour=discord.Colour.red()
        )
        e.add_field(name='Conversation ID', value=id)
        resp = await ctx.send(embed=e)

    @tasks.loop(minutes=1)
    async def auto_unsummon(self):
        """Automatically close inactive frames."""

        logger.debug('Checking auto unsummon...')

        for summon in self.summons.values():
            # Get time of last activity in the frame
            last = summon.last_activity.created_at

            logger.debug(
                'Last activity in %i was "%s"',
                summon.channel.id,
                summon.last_activity.clean_content
            )

            # Check if it was over 2 minutes ago
            if last <= datetime.now() - timedelta(minutes=2):
                # Close the frame
                logger.info(
                    'Automatically closing summon frame %i after inactivity',
                    summon.channel.id
                )

                # Get conversation ID
                id = self.conv_id(summon.resp)

                # Unsummon
                self.summons[summon.channel.id] = None

                # Send a notice to the channel
                e = discord.Embed(
                    title='Summon frame expired',
                    description=(
                        'I am no longer responding to messages in this channel.'
                        ' This frame was automatically closed after 2 minutes'
                        ' of inactivity.'
                    ),
                    colour=discord.Colour.red()
                )
                e.add_field(name='Conversation ID', value=id)
                resp = await summon.channel.send(embed=e)

    @auto_unsummon.before_loop
    async def before_auto_unsummon(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, msg):
        """
        Process a message and send a chatbot response to the channel.

        If the bot doesn't understand, no message will be sent.
        """

        logger.info('Received message "%s"', msg.clean_content)

        # Check if the author is a bot / system message
        if msg.author.bot or msg.type != discord.MessageType.default:
            logger.info('Author is a bot, ignoring')
            return

        # Check if this channel is active
        if not self.active_for(msg):
            logger.info('Channel is inactive, ignoring')
            return

        # Trigger a typing indicator while chatterbot processes
        await msg.channel.trigger_typing()

        # Update summon
        summon = self.summons[msg.channel.id]
        summon.last_activity = msg

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
            resp = await msg.channel.send(response.text)
            summon.last_activity = resp

    def conv_id(self, msg):
        """Get a conversation ID for the given message."""

        # Find the relevant Summon object
        summon = self.summons[msg.channel.id]
        # Get timestamp
        timestamp = summon.resp.created_at.timestamp()

        # Combine into full ID
        return f'{msg.channel.id}-{timestamp}'

    def active_for(self, msg):
        """Check if the bot should respond to the given message."""

        # Find the channel's Summon object
        summon = self.summons.get(msg.channel.id)

        if summon is None:
            # Not summoned
            return False

        # Check if the message is after the summon frame opened
        return msg.created_at > summon.resp.created_at

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
            conversation=self.conv_id(msg),
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
            oldest_first=False,
            before=msg,
            # Limit to messages within timeframe
            after=msg.created_at - timedelta(minutes=minutes)
        ).flatten()

        if len(prev) > 0:
            # We found a previous message
            if self.active_for(prev[0]):
                # Valid!
                logger.info('Found "%s"', prev[0].clean_content)
                return  prev[0].clean_content
            else:
                # The message is from before the summon frame opened
                logger.info('No message found within this frame')
        else:
            # We didn't find any messages
            logger.info('No message found')


def setup(bot):
    bot.add_cog(Chat(bot))
