"""
The embedder interface, and a hash embedder for tests.

Documents and queries have separate methods, because some models encode them
differently, such as with a prefix on queries. BGE-M3 encodes both the same
way.
"""

import hashlib
import math
from collections.abc import Sequence
from typing import Protocol

from hangar.core.errors import HangarError


class EmbedError(HangarError):
    """
    Chunks that couldn't be embedded, or vectors that don't match them.
    """


class Embedder(Protocol):
    """
    Turns texts into vectors.

    Attributes:
        model_id: The model, such as ``BAAI/bge-m3``.
        revision: The model's revision, such as its commit hash.
        dimension: How many values each vector has.
        normalized: Whether the vectors have unit length.
    """

    model_id: str
    revision: str
    dimension: int
    normalized: bool

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """
        Turn document texts, such as chunks, into vectors.

        Args:
            texts: The texts to embed.

        Returns:
            One vector per text, in the same order.
        """
        ...

    def embed_query(self, text: str) -> list[float]:
        """
        Turn a question into a vector, to search the document vectors.

        Args:
            text: The question.

        Returns:
            Its vector.
        """
        ...


class HashEmbedder:
    """
    Turns each text into a vector derived from its SHA-256. For tests.

    The same text always gives the same unit-length vector, and different
    texts give unrelated vectors, so tests can check what the pipeline does
    with vectors without loading a model. The vectors carry no meaning.

    Attributes:
        model_id: Always ``hash``.
        revision: The version of the hashing scheme, ``1``.
        dimension: How many values each vector has.
        normalized: Always True.
    """

    def __init__(self, dimension: int = 8) -> None:
        """
        Set up the embedder.

        Args:
            dimension: How many values each vector has.
        """
        self.model_id = "hash"
        self.revision = "1"
        self.dimension = dimension
        self.normalized = True

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """
        Turn texts into vectors.

        Args:
            texts: The texts to embed.

        Returns:
            One unit-length vector per text, in the same order.
        """
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """
        Turn a question into a vector, the same way as a document.

        Args:
            text: The question.

        Returns:
            Its unit-length vector.
        """
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        # Each value comes from the hash of its position and the text, mapped
        # to the range from -1 to 1.
        values = []

        for index in range(self.dimension):
            digest = hashlib.sha256(f"{index}|{text}".encode()).digest()
            values.append(int.from_bytes(digest[:8]) / 2**63 - 1)

        length = math.sqrt(sum(value * value for value in values))

        return [value / length for value in values]
