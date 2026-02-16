from axyn.filters import is_direct
from axyn.handlers import Handler
from opentelemetry.trace import get_tracer


_tracer = get_tracer(__name__)


class ConsentHandler(Handler):
    async def handle(self):
        """
        If the message directly addresses Axyn, and the author has not met Axyn
        before, then send them a consent prompt.
        """

        with _tracer.start_as_current_span(
            "send consent introduction if needed",
            attributes=self._attributes(),
        ) as span:
            if not is_direct(self.client, self.message):
                span.add_event("Cancelling because the message is not direct")
                return

            async with self.client.database_manager.session() as session:
                await self.client.consent_manager.send_introduction(
                    session,
                    self.message.author,
                )
                await session.commit()

