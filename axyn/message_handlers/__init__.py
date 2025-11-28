from abc import ABC, abstractmethod


class MessageHandler(ABC):
    def __init__(self, client, message):
        self.client = client
        self.message = message

    @abstractmethod
    async def handle(self):
        """Do whatever handling is required for this message."""
