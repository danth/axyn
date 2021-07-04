import logging
from abc import ABC, abstractmethod


class ReactionHandler(ABC):
    def __init__(self, client, reaction, reaction_user):
        self.client = client
        self.reaction = reaction
        self.reaction_user = reaction_user

        # Each instance has its own logger
        self.logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}.{self.reaction.message.id}"
        )
        self.logger.info(
            'Received reaction %s on "%s"',
            self.reaction.emoji,
            self.reaction.message.clean_content,
        )

    @abstractmethod
    async def handle(self):
        """Do whatever handling is required for this reaction."""
