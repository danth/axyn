import logging

from chatbot.vector import average_vector
from chatbot.ngtinit import statements_index, reactions_index
from models import Statement, Reaction


# Set up logging
logger = logging.getLogger(__name__)


def train_statement(text, responding_to, session):
    """
    Train the given statement into the index.

    :param text: Text to add.
    :param responding_to: The text this statement was in response to.
    :param session: Database session to use for insertions.
    """
    responding_to_vector = average_vector(responding_to)
    # Add vector to NGT index
    ngt_id = statements_index.insert(responding_to_vector)
    statements_index.build_index()
    statements_index.save()

    # Add response text to database
    session.add(Statement(ngt_id=ngt_id, text=text))
    session.commit()


def train_reaction(emoji, responding_to, session):
    """
    Train the given reaction into the index.

    :param text: Reaction emoji to add.
    :param responding_to: The text this reaction was added to.
    :param session: Database session to use for insertions.
    """
    responding_to_vector = average_vector(responding_to)
    # Add vector to NGT index
    ngt_id = reactions_index.insert(responding_to_vector)
    reactions_index.build_index()
    reactions_index.save()

    # Add reaction to database
    session.add(Reaction(ngt_id=ngt_id, emoji=emoji))
    session.commit()
