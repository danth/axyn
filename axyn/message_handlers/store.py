from axyn.database import MessageRecord, MessageRevisionRecord
from axyn.message_handlers import MessageHandler
from logdecorator import log_on_start
from logging import INFO, getLogger


class Store(MessageHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._logger = getLogger(__name__)

    async def handle(self):
        """Store this message."""

        if self.message.flags.ephemeral:
            self._logger.info(f"Not storing {self.message.id} because it is ephemeral")
            return

        if self.client.consent_manager.has_consented(self.message.author):
            self._store_full()
        else:
            self._store_redacted()

    @log_on_start(INFO, 'Storing full version of {self.message.id}')
    def _store_full(self):
        """Store this message in full."""

        with self.client.database_manager.session() as session:
            session.merge(MessageRevisionRecord.from_message(self.message))

    @log_on_start(INFO, 'Storing redacted version of {self.message.id}')
    def _store_redacted(self):
        """
        Store a redacted version of this message.

        In other words, record the fact that a message existed at this point in
        time, but do not store any of its content.

        Dropping these messages entirely would create discontinuities in the
        history, potentially leading us to believe that messages are related
        when they are in fact separate. It would also increase the average
        delay between messages.
        """

        with self.client.database_manager.session() as session:
            session.merge(MessageRecord.from_message(self.message))

