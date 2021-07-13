import logging
from abc import ABC, abstractmethod

from logdecorator import log_on_start


class ReactionHandler(ABC):
    @log_on_start(
        logging.INFO,
        'Received reaction {reaction.emoji} on "{reaction.message.clean_content}"',
    )
    def __init__(self, client, reaction, reaction_user):
        self.client = client
        self.reaction = reaction
        self.reaction_user = reaction_user

    @abstractmethod
    async def handle(self):
        """Do whatever handling is required for this reaction."""
