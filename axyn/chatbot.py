import os
import random
from dataclasses import dataclass

import ngtpy
import spacy

from axyn.database import DatabaseManager, ResponseRecord


def _load_spacy_model(model):
    """
    Load a SpaCy model by name.

    :param model: Name of the model to load, or an already-loaded model which is
        simply passed through.
    """

    if isinstance(model, str):
        return spacy.load(model, exclude=["ner"])

    return model


@dataclass
class Message:
    """
    A piece of text.

    :param text: The text of the message.
    :param metadata: An arbitrary string which can be retrieved when the
        message is chosen as a response.
    """

    text: str
    metadata: str = None


class Responder:
    """
    Holds a database connection and handles learning and producing responses.

    :param directory: Path to a folder which stores the index for this responder.
    :param database: Database connection used to store responses.
    :param model: SpaCy model, or the name of one to be loaded.
    """

    def __init__(self, directory: str, database: DatabaseManager, spacy_model="en_core_web_md"):
        self._batch_responses = list()
        self._index = self._load_index(directory)
        self._database = database
        self._spacy_model = _load_spacy_model(spacy_model)

    def _load_index(self, directory: str):
        """
        Create or open the NGT index.

        :param directory: Path to a folder which stores the index.
        """

        if not os.path.exists(directory):
            ngtpy.create(directory, dimension=300)  # Spacy word vectors are 300D

        return ngtpy.Index(directory)

    def get_all_responses(self, text):
        """
        Return all relevant responses to a prompt along with their distance.

        The distance returned gets closer to 0 the more confident the response is.
        There is no hard limit to how large the distance can be, however distances
        tend to range between 0 and 10.

        Note that this only returns messages which are linked to the same
        vector, so their distances are all the same.

        :returns: (list of Message instances, distance)
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

        with self._database.session() as session:
            # Get the known responses to this vector
            responses = (
                session
                    .query(ResponseRecord)
                    .filter(ResponseRecord.ngt_id == match_id)
                    .all()
            )

            # Convert each Response to a Message
            messages = [Message(response.response, response.meta) for response in responses]

        return messages, distance

    def get_response(self, text):
        """
        Return the most confident response to a prompt.

        The distance returned gets closer to 0 the more confident the response is.
        There is no hard limit to how large the distance can be, however distances
        tend to range between 0 and 10.

        :param text: The prompt to respond to.
        :returns: Tuple of (message, distance).
        """

        messages, distance = self.get_all_responses(text)

        if messages:
            return random.choice(messages), distance
        else:
            return None, distance

    def add_response(self, prompt, message):
        """
        Process a response pair without saving it immediately.

        The response won't be available as an output from ``get_response``
        until ``commit_responses`` is called.

        :param prompt: The text this is in response to.
        :param message: The response to be learned. This can be a simple string, or
            an instance of ``Message`` if you would like to include metadata.
        """

        if isinstance(message, str):
            message = Message(message)

        vector = self._average_vector(prompt)
        self._batch_responses.append((vector, message))

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

        with self._database.session() as session:
            for vector, message in self._batch_responses:
                session.add(
                    ResponseRecord(
                        ngt_id=self._get_index_id(vector),
                        response=message.text,
                        meta=message.metadata,
                    )
                )

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
