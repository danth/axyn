from spacy import displacy
import io
import hashlib
import nltk
import cairosvg

import discord
from discord.ext import commands
from chatbot.nlploader import nlp


nltk.download('punkt')
sent_tokenizer = nltk.data.load('tokenizers/punkt/english.pickle')


def render(sentences):
    """Render the given sentences with displaCy, to SVGs."""

    for sent in sentences:

        # Render sentence as SVG
        doc = nlp(sent, disable=['ner'])
        svg = displacy.render(
            doc,
            style='dep',
            options={
                'compact': True,
                'color': 'green',
                'font': 'monospace'
            }
        )

        # Convert to PNG image (returns bytestring)
        image = cairosvg.svg2png(bytestring=svg.encode())

        # Hash text to create file name
        hash_object = hashlib.md5(sent.encode())
        file_name = hash_object.hexdigest() + '.png'

        yield discord.File(
            io.BytesIO(image),
            filename=file_name
        )


class Analyse(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def analyse(self, ctx, *, text):
        """
        Render a dependency graph for the given text using displaCy.

        Each sentence of the text will be uploaded as a separate image.
        """

        # Split sentences
        sentences = sent_tokenizer.tokenize(text)

        # Render to SVG with displaCy
        for file in render(sentences):
            # Send each image as it is generated
            await ctx.send(file=file)


def setup(bot):
    bot.add_cog(Analyse(bot))
