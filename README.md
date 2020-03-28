![Axyn logo](images/axyn.png)

# Axyn

[![Maintainability](https://api.codeclimate.com/v1/badges/a86290ca2ee89d387756/maintainability)](https://codeclimate.com/github/AlphaMycelium/axyn/maintainability)

A simple Discord chatbot.

This was originally powered by [Chatterbot](https://github.com/gunthercox/ChatterBot),
however response times were getting far too slow and I was customizing the
behaviour a lot. In the end I wrote my own implementation following the same
basic principles (database of known responses, search for responses which might
match, find the closest match based on a distance calculation). It has a lot
less features and is mainly designed for performance.

**Support / testing server: https://discord.gg/4twAd8C**

## Chat

You can chat to Axyn at any time by sending it a DM.

## Analysis

Axyn provides the command `a!analyse`, which allows to run a lexical analysis
on a sentence or paragraph of text and send the results to Discord as an image.
This is powered by DisplaCy. A reference of what the different dependency types
mean is available [here](https://spacy.io/api/annotation#dependency-parsing-english).
