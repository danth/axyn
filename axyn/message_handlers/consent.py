from axyn.filters import is_direct
from axyn.message_handlers import MessageHandler


class Consent(MessageHandler):
    async def handle(self):
        """
        If the message directly addresses Axyn, and the author has not met Axyn
        before, then send them a consent prompt.
        """

        if not is_direct(self.client, self.message):
            return

        with self.client.database_manager.session() as session:
            await self.client.consent_manager.send_introduction(
                self.message.author,
                session,
            )

