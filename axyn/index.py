from axyn.database import IndexRecord, MessageRecord, MessageRevisionRecord
from axyn.filters import is_command
from axyn.preprocessor import preprocess
from discord import Client
from discord.ext.tasks import loop
from logging import getLogger
from ngtpy import create as create_ngt, Index as load_ngt
from numpy import quantile
from os import path
from spacy import load as load_spacy
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
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

    async def get_responses(
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

    def _is_valid(self, message: MessageRecord) -> bool:
        """
        Return whether the given message is worth indexing.

        This excludes messages which have no content stored, or whose content
        is spam, to avoid returning useless results.
        """

        if not message.revisions:
            self._logger.debug(f"{message.message_id} is not valid because no revisions were saved")
            return False

        for revision in message.revisions:
            if is_command(revision.content):
                self._logger.debug(f"{message.message_id} is not valid because a revision looks like a command")
                return False

        return True

    def _is_valid_response(self, message: MessageRecord) -> bool:
        """
        Return whether the given message is worth indexing as a response.

        This excludes the same things as ``_is_valid``, and also excludes
        messages generated by bots.
        """

        if not message.author.human:
            self._logger.debug(f"{message.message_id} is not valid because its author is not human")
            return False

        return self._is_valid(message)

    def _is_valid_prompt(
        self,
        current_message: MessageRecord,
        prompt_message: MessageRecord
    ) -> bool:
        """
        Return whether the given message is worth indexing as a prompt for the
        given response.

        This excludes the same things as ``_is_valid``, and also excludes cases
        where a user replies to themself.

        This does not do any checks on the response, which is assumed to
        already be valid.
        """

        if prompt_message.author == current_message.author:
            self._logger.debug(f"{current_message.message_id} is not valid because {prompt_message.message_id} has the same author")
            return False

        return self._is_valid(prompt_message)

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

        if not self._is_valid_response(current_message):
            return None

        # If there is an explicit reply, we can just short circuit to that.
        if current_message.reference is not None:
            if self._is_valid_prompt(current_message, current_message.reference):
                return current_message.reference
            else:
                return None

        # Otherwise, query up to 100 messages coming before the current message,
        # with the most recent sorted at the start of the list.
        history = (
            session
            .execute(
                select(MessageRecord)
                .where(MessageRecord.created_at < current_message.created_at)
                .order_by(desc(MessageRecord.created_at))
                .limit(100)
            )
            .scalars()
            .all()
        )

        try:
            previous_message = history[0]
        except IndexError:
            self._logger.debug(f"{current_message.message_id} is not valid because no previous messages were found")
            return None

        if not self._is_valid_prompt(current_message, previous_message):
            return None

        # Group messages into consecutive pairs, and for valid pairs, calculate the
        # time in seconds between the messages being sent.
        delays = []

        for current, prompt in zip(history, history[1:]):
            if not self._is_valid_prompt(current, prompt):
                continue

            # In addition to the usual checks, also skip over bots since they
            # usually reply immediately, which skews the results.
            if not current.author.human:
                continue

            delay = (current.created_at - prompt.created_at).total_seconds()
            delays.append(delay)

        # At least one pair is required for the following calculation.
        if not delays:
            self._logger.debug(
                f"{current_message.message_id} is not valid because not enough previous messages were found "
                f"(got {len(history)} messages, in which {len(delays)} valid pairs were found)"
            )
            return None

        # Calculate the upper quartile of the delays; if the delay between the
        # current message and the previous message is less than this then we can
        # assume that they are part of the same conversation.
        maximum_delay = quantile(delays, 0.75)

        delay = (previous_message.created_at - current_message.created_at).total_seconds()

        if delay > maximum_delay:
            self._logger.debug(
                f"{current_message.message_id} is not valid because the previous message was too long ago "
                f"(expected <= {maximum_delay}, got {delay})"
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

