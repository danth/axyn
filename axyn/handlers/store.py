from axyn.database import (
    ConsentResponse,
    MessageRecord,
    MessageRevisionRecord,
)
from axyn.handlers import Handler
from opentelemetry.trace import get_tracer


_tracer = get_tracer(__name__)


class StoreHandler(Handler):
    async def handle(self):
        """
        Store this message.

        Whether or not the user has consented, we must store the fact that a
        message existed at this point in time. Dropping such messages entirely
        would create discontinuities in the history, potentially leading us to
        believe that other messages are related when they are in fact separate.
        It would also increase the average delay between messages.
        """

        with _tracer.start_as_current_span(
            "store message",
            attributes=self._attributes(),
        ) as span:
            async with self.client.database_manager.session() as session:
                consent = await self.client.consent_manager.get_response(
                    session,
                    self.message.author,
                )

                if consent == ConsentResponse.NO:
                    span.add_event("Storing redacted version")
                    await MessageRecord.insert(session, self.message)
                else:
                    span.add_event(f"Storing full version")
                    await MessageRevisionRecord.insert(session, self.message)

                await session.commit()

