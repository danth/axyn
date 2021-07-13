import logging
from abc import ABC, abstractmethod

from logdecorator import log_on_start


class MessageHandler(ABC):
    @log_on_start(logging.INFO, 'Received message "{message.clean_content}"')
    def __init__(self, client, message):
        self.client = client
        self.message = message

    @abstractmethod
    async def handle(self):
        """Do whatever handling is required for this message."""
