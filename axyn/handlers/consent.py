from axyn.filters import is_direct
from axyn.handlers import Handler


class ConsentHandler(Handler):
    async def handle(self):
        """
        If the message directly addresses Axyn, and the author has not met Axyn
        before, then send them a consent prompt.
        """

        if not await is_direct(self.client, self.message):
            return

        async with self.client.database_manager.session() as session:
            await self.client.consent_manager.send_introduction(
                session,
                self.message.author,
            )

            await session.commit()

