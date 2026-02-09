from __future__ import annotations
from axyn.database import (
    ConsentResponse,
    MessageRecord,
    MessageRevisionRecord,
)
from axyn.handlers import Handler
from logging import getLogger
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from discord import Message


class StoreHandler(Handler):
    def __init__(self, client: AxynClient, message: Message):
        super().__init__(client, message)

        self._logger = getLogger(__name__)

    async def handle(self):
        """
        Store this message.

        Whether or not the user has consented, we must store the fact that a
        message existed at this point in time. Dropping such messages entirely
        would create discontinuities in the history, potentially leading us to
        believe that other messages are related when they are in fact separate.
        It would also increase the average delay between messages.
        """

        async with self.client.database_manager.session() as session:
            consent = await self.client.consent_manager.get_response(session, self.message.author)

            if consent == ConsentResponse.NO:
                self._logger.info(f"Storing redacted version of {self.message.id}")
                await MessageRecord.insert(session, self.message)
            else:
                self._logger.info(f"Storing full version of {self.message.id}")
                await MessageRevisionRecord.insert(session, self.message)

            await session.commit()

