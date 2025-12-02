from __future__ import annotations
from axyn.database import IndexRecord, MessageRecord, MessageRevisionRecord
from axyn.filters import is_valid_prompt, is_valid_response
from axyn.history import get_history, get_delays
from axyn.preprocessor import preprocess
from discord.ext.tasks import loop
from fastembed import TextEmbedding
from logging import getLogger
from ngtpy import create as create_ngt, Index
from os import path
from sqlalchemy import select, desc
from statistics import StatisticsError
from typing import TYPE_CHECKING, cast


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from numpy import dtype, float32, ndarray
    from sqlalchemy.ext.asyncio import AsyncSession
    from typing import Optional, AsyncGenerator, Sequence

    Vector = ndarray[tuple[384], dtype[float32]]


class IndexManager:
    def __init__(self, client: AxynClient, directory: str):
        if not path.exists(directory):
            create_ngt(
                directory,
                dimension=384,
                distance_type="Cosine",
            )

        self._client = client
        self._index = Index(directory)
        self._model = TextEmbedding()
        self._logger = getLogger(__name__)

    async def setup_hook(self):
        self._update_index.start()

    async def get_response_groups(
        self,
        prompt: str,
        session: AsyncSession
    ) -> AsyncGenerator[tuple[Sequence[MessageRevisionRecord], float]]:
        """
        Get a selection of possible responses to the given message content.

        Responses are grouped by the cosine distance between their original
        prompt and the current prompt. This is a useful metric to decide
        whether the response is relevant or not. It always falls in the range
        ``[0, 2]``, where zero is the most relevant. The generator produces
        response groups in ascending order.
        """

        vector = self._vector(prompt)
        results = self._index.search(vector, size=100)

        for index_id, distance in results:
            result = await session.execute(
                select(MessageRevisionRecord)
                .join(IndexRecord, IndexRecord.message_id == MessageRevisionRecord.message_id)
                .where(IndexRecord.index_id == index_id)
            )
            revisions = result.scalars().all()

            yield revisions, distance

    def _vector(self, content: str) -> Vector:
        """Return the vector for the given message content."""

        content = preprocess(self._client, content)
        vectors = self._model.embed([content])
        vector = list(vectors)[0]
        return cast("Vector", vector)

    def _insert(self, vector: Vector, batch: dict[bytes, int]) -> int:
        """
        Insert a vector into the index.

        Compared to the standard insert method, this method has deduplication,
        so identical vectors are given the same ID.

        The provided dictionary is used to keep track of vectors that have been
        inserted since the index was last built, since we cannot query those
        via standard methods.
        """

        # Convert the numpy array to bytes so we can use it as a dictionary key
        vector_hash = vector.tobytes()

        # Check the unbuilt vectors first
        try:
            return batch[vector_hash]
        except KeyError:
            pass

        # Query the index for this vector
        result = self._index.search(vector, size=1)

        if result and result[0][1] == 0:
            # This vector already exists, return its id
            return result[0][0]
        else:
            # Add vector to the index
            index_id = self._index.insert(vector)
            batch[vector_hash] = index_id
            return index_id

    @loop(minutes=1)
    async def _update_index(self):
        """Scan the database for new responses and add them to the index."""

        self._logger.info("Updating index")

        async with self._client.database_manager.session() as session:
            result = await session.execute(
                select(MessageRecord)
                .where(MessageRecord.index == None)
            )
            messages = result.scalars().all()

            batch: dict[bytes, int] = {}

            for message in messages:
                self._logger.debug(f"Checking {message.message_id}")

                prompt = await self._get_prompt_revision(session, message)

                if prompt is None:
                    # Mark the message as processed, but not added to the index.
                    session.add(IndexRecord(message=message, index_id=None))
                else:
                    self._logger.debug(f'Indexing {message.message_id} under "{prompt.content}"')
                    vector = self._vector(prompt.content)
                    index_id = self._insert(vector, batch)
                    session.add(IndexRecord(message=message, index_id=index_id))

            self._index.build_index()
            self._index.save()

            await session.commit()

    async def _get_prompt_message(
        self,
        session: AsyncSession,
        current_message: MessageRecord
    ) -> Optional[MessageRecord]:
        """
        Query the database for a prompt corresponding to the given response.

        The input and output of this method are filtered with
        ``_is_valid_response`` and ``_is_valid_prompt`` respectively, to avoid
        indexing low quality data. Invalid messages will result in ``None``.
        """

        if not await is_valid_response(session, current_message):
            return None


        if current_message.reference_id is not None:
            result = await session.execute(
                select(MessageRecord)
                .where(MessageRecord.message_id == current_message.reference_id)
            )
            reference = result.scalar_one()

            if await is_valid_prompt(session, current_message, reference):
                return reference
            else:
                return None

        history = await get_history(
            session,
            current_message.channel_id,
            current_message.created_at,
        )

        try:
            previous_message = history[0]
        except IndexError:
            self._logger.debug(f"{current_message.message_id} is not valid because no previous messages were found")
            return None

        if not await is_valid_prompt(session, current_message, previous_message):
            return None

        try:
            _, _, upper_quartile = await get_delays(session, history)
        except StatisticsError:
            self._logger.debug(f"{current_message.message_id} is not valid because not enough previous messages were found")
            return None

        delay = (previous_message.created_at - current_message.created_at).total_seconds()

        if delay > upper_quartile:
            self._logger.debug(
                f"{current_message.message_id} is not valid because the previous message was too long ago "
                f"(expected <= {upper_quartile}, got {delay})"
            )
            return None

        return previous_message

    async def _get_prompt_revision(
        self,
        session: AsyncSession,
        current_message: MessageRecord
    ) -> Optional[MessageRevisionRecord]:
        """
        Query the database for a prompt corresponding to the given response.

        This behaves identically to ``_get_prompt_message``, but selects a
        specific revision of the prompt depending on the time the response was
        sent.
        """

        prompt_message = await self._get_prompt_message(session, current_message)

        if prompt_message is None:
            return None

        # Find the most recent edit which existed before the reply was sent.
        result = await session.execute(
            select(MessageRevisionRecord)
            .where(MessageRevisionRecord.message == prompt_message)
            .where(MessageRevisionRecord.edited_at < current_message.created_at)
            .order_by(desc(MessageRevisionRecord.edited_at))
            .limit(1)
        )
        return result.scalar()

