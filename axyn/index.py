from axyn.database import IndexRecord, MessageRecord, MessageRevisionRecord
from axyn.filters import is_valid_prompt, is_valid_response
from axyn.history import get_history, get_delays
from axyn.preprocessor import preprocess
from discord import Client
from discord.ext.tasks import loop
from logging import getLogger
from ngtpy import create as create_ngt, Index as load_ngt
from os import path
from spacy import load as load_spacy
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from statistics import StatisticsError
from typing import Optional, Sequence


class IndexManager:
    def __init__(self, client: Client, directory: str):
        if not path.exists(directory):
            create_ngt(directory, dimension=300)  # Spacy word vectors are 300D

        self._client = client
        self._index = load_ngt(directory)
        self._model = load_spacy("en_core_web_md", exclude=["ner"])
        self._logger = getLogger(__name__)

    def setup_hook(self):
        self._update_index.start()

    def get_responses(
        self,
        prompt: str,
        session: Session
    ) -> tuple[Sequence[MessageRevisionRecord], float]:
        """
        Get a selection of possible responses to the given message content.

        Also returns a distance metric which estimates how confident the
        responses are. Better responses will have a lower distance, but the
        exact value is meaningless.
        """

        vector = self._vector(prompt)

        results = self._index.search(vector, 1)

        try:
            index_id, distance = results[0]
        except IndexError:
            # No results were found; this usually means the index was empty.
            return [], float("inf")

        revisions = (
            session
            .execute(
                select(MessageRevisionRecord)
                .join(IndexRecord, IndexRecord.message_id == MessageRevisionRecord.message_id)
                .where(IndexRecord.index_id == index_id)
            )
            .scalars()
            .all()
        )

        return revisions, distance

    def _vector(self, content: str):
        """Return the vector for the given message content."""

        content = preprocess(self._client, content)
        document = self._model(content, disable=["ner"])

        try:
            # Excluding punctuation
            vectors = [
                token.vector
                for token in document
                if token.has_vector and not token.is_punct
            ]
            return sum(vectors) / len(vectors)

        except ZeroDivisionError:
            # Including punctuation
            return document.vector

    def _insert(self, vector, batch: dict[bytes, int]) -> int:
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
        result = self._index.search(vector, 1)

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

        with self._client.database_manager.session() as session:
            messages = (
                session.execute(
                    select(MessageRecord)
                    .where(MessageRecord.index == None)
                )
                .scalars()
                .all()
            )

            batch = {}

            for message in messages:
                self._logger.debug(f"Checking {message.message_id}")

                prompt = self._get_prompt_revision(session, message)

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

    def _get_prompt_message(
        self,
        session: Session,
        current_message: MessageRecord
    ) -> Optional[MessageRecord]:
        """
        Query the database for a prompt corresponding to the given response.

        The input and output of this method are filtered with
        ``_is_valid_response`` and ``_is_valid_prompt`` respectively, to avoid
        indexing low quality data. Invalid messages will result in ``None``.
        """

        if not is_valid_response(current_message):
            return None

        if current_message.reference is not None:
            if is_valid_prompt(current_message, current_message.reference):
                return current_message.reference
            else:
                return None

        history = get_history(
            session,
            current_message.channel,
            current_message.created_at,
        )

        try:
            previous_message = history[0]
        except IndexError:
            self._logger.debug(f"{current_message.message_id} is not valid because no previous messages were found")
            return None

        if not is_valid_prompt(current_message, previous_message):
            return None

        try:
            _, _, upper_quartile = get_delays(history)
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

    def _get_prompt_revision(
        self,
        session: Session,
        current_message: MessageRecord
    ) -> Optional[MessageRevisionRecord]:
        """
        Query the database for a prompt corresponding to the given response.

        This behaves identically to ``_get_prompt_message``, but selects a
        specific revision of the prompt depending on the time the response was
        sent.
        """

        prompt_message = self._get_prompt_message(session, current_message)

        if prompt_message is None:
            return None

        # Find the most recent edit which existed before the reply was sent.
        return (
            session
            .execute(
                select(MessageRevisionRecord)
                .where(MessageRevisionRecord.message == prompt_message)
                .where(MessageRevisionRecord.edited_at < current_message.created_at)
                .order_by(desc(MessageRevisionRecord.edited_at))
                .limit(1)
            )
            .scalar()
        )

