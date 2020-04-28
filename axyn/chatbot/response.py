import logging

from mathparse import mathparse

from chatbot.caps import capitalize
from chatbot.vector import average_vector
from chatbot.ngtinit import statements_index, reactions_index
from models import Statement, Reaction


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
    except mathparse.PostfixTokenEvaluationException:
        return None
    except KeyError:
        return None


def get_closest_vector(text, index):
    """
    Get the closest matching response from the index.

    :param text: Text we are comparing against.
    :param index: NGT index to query from.
    :returns: Tuple of (id, distance).
    """
    text_vector = average_vector(text)

    # Nearest neighbour search to find the closest stored vector
    results = index.search(text_vector, 1)
    if len(results) == 0:
        # The index is empty!
        return None, None

    # Unpack the first and only result
    match_id, distance = results[0]
    logger.info(
        'Selected s%i as closest match, at distance %.3f',
        match_id, distance
    )
    return match_id, distance


def confidence(distance):
    """
    Convert the distance between two document vectors to a confidence.

    :param distance: Euclidean distance.
    :returns: Confidence value ranging from 0 (low similarity) to
        1 (high similarity).
    """
    # 0.6 has no specific meaning, it was chosen to scale the results to a
    # sensible value based on observations
    # https://www.wolframalpha.com/input/?i=plot+1%2F%281%2B0.6d%29+from+0+to+5
    return 1 / (1 + (0.6 * distance))


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

    # Find closest matching vector
    match_id, distance = get_closest_vector(text, statements_index)
    if match_id is None:
        return None, 0

    # Get the associated response text
    match = session.query(Statement).filter(Statement.ngt_id == match_id).one()
    return capitalize(match.text), confidence(distance)


def get_reaction(text, session):
    """
    Generate a reaction emoji to the given text.

    The confidence of the returned reaction is based on the similarity of the
    given text and the text it was originally added to.

    :param text: Text to react to.
    :param session: Database session to use for queries.
    :returns: Tuple of (emoji, confidence).
    """
    # Find closest matching vector
    match_id, distance = get_closest_vector(text, reactions_index)
    if match_id is None:
        return None, 0

    # Get the associated reaction
    match = session.query(Reaction).filter(Reaction.ngt_id == match_id).one()
    return match.emoji, confidence(distance)
