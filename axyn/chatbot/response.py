import logging
import random
from statistics import mode, StatisticsError

from sqlalchemy import or_
from mathparse import mathparse

from chatbot.caps import capitalize
from chatbot.models import Statement, Reaction
from chatbot.pairs import get_pairs
from chatbot.nlploader import nlp


# Set up logging
logger = logging.getLogger(__name__)


def process_as_math(text):
    """
    Attempt to process the text as a mathematical evaluation using mathparse.

    :returns: Response text, or None if the input cannot be parsed as math.
    """
    try:
        expression = mathparse.extract_expression(text, language='ENG')
        result = mathparse.parse(expression, language='ENG')
        return f'{expression} = {result}'
    except  mathparse.PostfixTokenEvaluationException:
        return None


def get_closest_match(text, options):
    """
    Get the closest match to some text given a list of options.

    :param text: Text we are looking for a match to.
    :param options: List of options to try. It is highly recommended to
        deduplicate this list to save processing time.
    :returns: Tuple of (match, similarity).
    """
    logger.debug(
        'Looking for closest match to "%s" in %i options',
        text, len(options)
    )
    text_doc = nlp(text)

    # Make a list of similarities corresponding to the options
    similarities = list()
    for option in options:
        similarity = text_doc.similarity(nlp(option))
        similarities.append(similarity)
        logger.debug('%d similar to "%s"', similarity, option)

    # Return the option with the highest similarity
    return max(
        zip(options, similarities),
        key=lambda o: o[1]
    )


def get_closest_matching_response(text, query_type, session):
    """
    Get the closest matching responding_to from the database.

    :param text: Text we are comparing against.
    :param query_type: Either Statement or Reaction.
    :param session: Database session to use for queries.
    :returns: Tuple of (match, confidence).
    """
    # Get bigram pairs for the text
    pairs = get_pairs(text)
    logger.debug('Bigram pairs: %s', ' '.join(pairs))

    # Query for statements which contain at least one similar bigram pair
    # Only get distinct values of responding_to to cut down on processing time
    search = [query_type.responding_to_bigram.contains(pair) for pair in pairs]
    responding_to_texts = session.query(Statement.responding_to) \
        .filter(or_(*search)).distinct().all()
    # Unpack result tuples
    responding_to_texts = [r for r, in responding_to_texts]

    if len(responding_to_texts) == 0:
        # No possible matches found
        logger.info('No possible matches found')
        return None, 0

    # Find the closest matching responding_to value
    match, confidence = get_closest_match(text, responding_to_texts)
    logger.info(
        'Selected "%s" as closest match to "%s" with confidence %d',
        match, text, confidence
    )
    return match, confidence


def get_response(text, session):
    """
    Generate a response to the given text.

    The confidence of the returned response is based on the similarity of the
    given text and the text it was originally in response to.

    :param text: Text to respond to.
    :param session: Database session to use for queries.
    :returns: Tuple of (response, confidence).
    """
    math_response = process_as_math(text)
    if math_response:
        # The text can be handled as a mathematical evaluation
        return math_response, 1

    match, confidence = get_closest_matching_response(text, Statement, session)
    if match is None:
        return None, 0

    # Find all statements which are responding_to the same text
    responses = session.query(Statement.text) \
        .filter(Statement.responding_to == match).all()
    # Unpack result tuples
    responses = [r for r, in responses]
    logger.debug(
        'There are %i possible responses to "%s"',
        len(responses), match
    )

    try:
        # Find the most frequent response
        selected_response = mode(responses)
        logger.info('Selected "%s" as mode response', selected_response)
    except StatisticsError:
        # No mode, select a random response
        selected_response = random.choice(responses)
        logger.info('Selected "%s" at random', selected_response)

    return capitalize(selected_response), confidence


def get_reaction(text, session):
    """
    Generate a reaction emoji to the given text.

    The confidence of the returned reaction is based on the similarity of the
    given text and the text it was originally added to.

    :param text: Text to react to.
    :param session: Database session to use for queries.
    :returns: Tuple of (emoji, confidence).
    """
    match, confidence = get_closest_matching_response(text, Reaction, session)
    if match is None:
        return None, 0

    # Find other reactions which react to the same text
    response_emojis = session.query(Reaction.emoji) \
        .filter(Reaction.responding_to == match)
    # Unpack result tuples
    response_emojis = [r for r, in response_emojis]
    logger.debug(
        'There are %i possible reactions to "%s"',
        len(response_emojis), match
    )

    try:
        # Find the most frequent reaction
        response_emoji = mode(response_emojis)
        logger.info('Selected %s as mode reaction', response_emoji)
    except StatisticsError:
        # No mode, select a random reaction
        response_emoji = random.choice(response_emojis)
        logger.info('Selected %s at random', response_emoji)

    return response_emoji, confidence
