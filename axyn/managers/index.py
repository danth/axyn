from __future__ import annotations
from axyn.database import MessageRecord, MessageRevisionRecord, get_path
from axyn.filters import is_valid_pair
from axyn.history import analyze_delays
from axyn.managers import Manager
from axyn.preprocessor import preprocess_index
from discord.ext.tasks import loop
from fastembed import TextEmbedding
from logging import getLogger
from ngtpy import create as create_ngt, Index
from os import path
from sqlalchemy import asc, select
from statistics import StatisticsError
from typing import TYPE_CHECKING, cast


if TYPE_CHECKING:
    from axyn.client import AxynClient
    from numpy import dtype, float32, ndarray
    from sqlalchemy.ext.asyncio import AsyncSession
    from typing import AsyncGenerator

    Vector = ndarray[tuple[384], dtype[float32]]


class IndexManager(Manager):
    def __init__(self, client: AxynClient):
        super().__init__(client)

        directory = get_path("index")

        if not path.exists(directory):
            create_ngt(
                directory,
                dimension=384,
                distance_type="Cosine",
            )

        self._index = Index(directory)
        self._model = TextEmbedding()
        self._logger = getLogger(__name__)

    async def setup_hook(self):
        self._update_index.start()

    def _vector(self, content: str) -> Vector:
        """Return the vector for the given message content."""

        content = preprocess_index(content)
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
        """Scan the database for new revisions and add them to the index."""

        self._logger.info("Updating index")

        async with self._client.database_manager.session() as session:
            revisions = await session.scalars(
                select(MessageRevisionRecord)
                .where(MessageRevisionRecord.index_id == None)
            )

            batch: dict[bytes, int] = {}

            for revision in revisions:
                vector = self._vector(revision.content)
                revision.index_id = self._insert(vector, batch)

            self._index.build_index()
            self._index.save()

            await session.commit()

    async def get_responses_to_text(
        self,
        session: AsyncSession,
        prompt_text: str,
    ) -> AsyncGenerator[tuple[MessageRevisionRecord, MessageRevisionRecord, float]]:
        """
        Get a selection of possible responses to the given text.

        This looks up existing prompts with similar text to the input, then for
        each of those, looks up a selection of possible responses.

        Each return value is a triple containing a prompt revision, response
        revision, and the distance between the prompt and the input text.

        Cosine distance is a useful metric to decide whether the response is
        relevant or not. It always falls in the range ``[0, 2]``, where zero
        is the most relevant. The generator always produces distances in
        ascending order.
        """

        vector = self._vector(prompt_text)
        results = self._index.search(vector, size=100)

        for index_id, distance in results:
            prompts = await session.scalars(
                select(MessageRevisionRecord)
                .where(MessageRevisionRecord.index_id == index_id)
            )

            for prompt in prompts:
                async for response in self.get_responses_to_revision(session, prompt):
                    yield prompt, response, distance

    async def get_responses_to_revision(
        self,
        session: AsyncSession,
        prompt_revision: MessageRevisionRecord,
    ) -> AsyncGenerator[MessageRevisionRecord]:
        """Get a selection of possible responses to the given revision."""

        prompt_message = await session.get_one(
            MessageRecord,
            prompt_revision.message_id,
        )

        references = await session.scalars(
            select(MessageRevisionRecord)
            .join(MessageRecord)
            .where(MessageRecord.reference_id == prompt_revision.message_id)
        )

        for reference in references:
            if await is_valid_pair(session, prompt_revision, reference):
                yield reference

        next_message = await session.scalar(
            select(MessageRecord)
            .where(MessageRecord.channel_id == prompt_message.channel_id)
            .where(MessageRecord.created_at > prompt_message.created_at)
            .where(MessageRecord.ephemeral.is_not(True))
            .order_by(asc(MessageRecord.created_at))
            .limit(1)
        )

        if next_message is None:
            return

        try:
            _, _, upper_quartile = await analyze_delays(
                session,
                next_message.author_id
            )
        except StatisticsError:
            self._logger.debug(
                f"({prompt_revision.revision_id}, next message) "
                "is not valid because not enough previous messages were found"
            )
            return

        delay = (next_message.created_at - prompt_message.created_at).total_seconds()

        if delay > upper_quartile:
            self._logger.debug(
                f"({prompt_revision.revision_id}, next message) "
                "is not valid because the time between messages was too long "
                f"(expected <= {upper_quartile}, got {delay})"
            )
            return

        revisions = await session.scalars(
            select(MessageRevisionRecord)
            .where(MessageRevisionRecord.message_id == next_message.message_id)
        )

        for revision in revisions:
            if await is_valid_pair(session, prompt_revision, revision):
                yield revision

