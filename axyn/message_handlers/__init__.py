import logging
from abc import ABC, abstractmethod


class MessageHandler(ABC):
    def __init__(self, bot, message):
        self.bot = bot
        self.message = message

        # Each instance has its own logger
        self.logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}.{self.message.id}"
        )
        self.logger.info('Received message "%s"', self.message.clean_content)

    @abstractmethod
    async def handle(self):
        """Do whatever handling is required for this message."""
