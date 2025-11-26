from discord import Client
import os
import ngtpy
import random
import spacy
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Optional, Sequence

from axyn.database import IndexRecord, MessageRecord, MessageRevisionRecord
from axyn.preprocessor import preprocess


def _load_spacy_model(model):
    """
    Load a SpaCy model by name.

    :param model: Name of the model to load, or an already-loaded model which is
        simply passed through.
    """

    if isinstance(model, str):
        return spacy.load(model, exclude=["ner"])

    return model


class Responder:
    """
    Holds a database connection and handles learning and producing responses.

    :param directory: Path to a folder which stores the index for this responder.
    :param database: Database connection used to store responses.
    :param model: SpaCy model, or the name of one to be loaded.
    """

    def __init__(self, directory: str, client: Client, spacy_model="en_core_web_md"):
        self._batch_responses = list()
        self._client = client
        self._index = self._load_index(directory)
        self._spacy_model = _load_spacy_model(spacy_model)

    def _load_index(self, directory: str):
        """
        Create or open the NGT index.

        :param directory: Path to a folder which stores the index.
        """

        if not os.path.exists(directory):
            ngtpy.create(directory, dimension=300)  # Spacy word vectors are 300D

        return ngtpy.Index(directory)

    def get_all_responses(self, text, session: Session) -> tuple[Sequence[MessageRevisionRecord], float]:
        """
        Return all relevant responses to a prompt along with their distance.

        The distance returned gets closer to 0 the more confident the response is.
        There is no hard limit to how large the distance can be, however distances
        tend to range between 0 and 10.

        Note that this only returns messages which are linked to the same
        vector, so their distances are all the same.

        :returns: (list of ``MessageRevisionRecord`` instances, distance)
        """

        # Convert the input to a vector
        input_vector = self._average_vector(text)

        # Find the closest vector for which we know a response
        matches = self._index.search(input_vector, 1)
        try:
            match_id, distance = matches[0]
        except IndexError:
            # No results were found, this most likely indicates an empty index
            return [], float("inf")

        # Get the known responses to this vector
        index_records = (
            session
            .execute(
                select(IndexRecord)
                .where(IndexRecord.index_id == match_id)
            )
            .scalars()
            .all()
        )

        messages = []

        for index_record in index_records:
            messages += index_record.message.revisions

        return messages, distance

    def get_response(self, text, session: Session) -> tuple[Optional[MessageRevisionRecord], float]:
        """
        Return the most confident response to a prompt.

        The distance returned gets closer to 0 the more confident the response is.
        There is no hard limit to how large the distance can be, however distances
        tend to range between 0 and 10.

        :param text: The prompt to respond to.
        :returns: Tuple of (message, distance).
        """

        messages, distance = self.get_all_responses(text, session)

        if messages:
            return random.choice(messages), distance
        else:
            return None, distance

    def add_response(self, prompt: MessageRevisionRecord, message: MessageRevisionRecord):
        """
        Process a response pair without saving it immediately.

        The response won't be available as an output from ``get_response``
        until ``commit_responses`` is called.

        :param prompt: The message this is in response to.
        :param message: The response to be learned.
        """

        vector = self._average_vector(preprocess(self._client, prompt.content))
        self._batch_responses.append((vector, message.message))

    def _get_index_id(self, vector):
        """
        Find the ID a vector will have in the NGT index.

        The vector is added to the index if it is not already present, however,
        the index is not rebuilt. We temporarily hold new vectors in
        ``self._unbuild_ids`` to prevent them being added twice.

        :param vector: Vector to get the ID of.
        """

        # Convert the numpy array to bytes so we can use it as a dictionary key
        vector_hash = vector.tobytes()
        if vector_hash in self._batch_vectors:
            # Vector is in unbuilt_ids, return it
            return self._batch_vectors[vector_hash]

        # Query the index for this vector
        result = self._index.search(vector, 1)
        if len(result) > 0 and result[0][1] == 0:
            # This vector already exists, return its id
            return result[0][0]
        else:
            # Add vector to the index
            index_id = self._index.insert(vector)
            self._batch_vectors[vector_hash] = index_id
            return index_id

    def commit_responses(self):
        """Save any responses which have not yet been written to the database."""

        self._batch_vectors = dict()

        with self._client.database_manager.session() as session:
            for vector, message in self._batch_responses:
                session.merge(IndexRecord(
                    message=message,
                    index_id=self._get_index_id(vector)
                ))

        self._index.build_index()
        self._index.save()

        del self._batch_vectors
        self._batch_responses = list()

    def learn_response(self, *args, **kwargs):
        """
        Add a response pair and save it immediately.

        Takes the same parameters as ``add_response``.

        Other unsaved responses will also be committed when you call this method.
        """

        self.add_response(*args, **kwargs)
        self.commit_responses()

    def _average_vector(self, text):
        """
        Convert a string to a vector based on its semantic meaning.

        Punctuation is ignored unless there are no other tokens present, in
        which case we include it.

        :param text: String to process.
        :returns: Vector representation of the text.
        """

        document = self._spacy_model(text, disable=["ner"])

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
