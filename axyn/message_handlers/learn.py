from axyn.database import MessageRevisionRecord
from axyn.message_handlers import MessageHandler
from logdecorator import log_on_start
from logging import INFO


class Learn(MessageHandler):
    async def handle(self):
        """Learn this message, if allowed."""

        if self.client.consent_manager.has_consented(self.message.author):
            self._learn()

    @log_on_start(INFO, 'Saving {self.message.id}')
    def _learn(self):
        """Learn this message."""

        with self.client.database_manager.session() as session:
            session.merge(MessageRevisionRecord.from_message(self.message))

