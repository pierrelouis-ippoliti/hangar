"""
The retriever interface, and a retriever with fixed results for tests.
"""

from collections.abc import Sequence
from typing import Protocol

from hangar.core.chunks import Chunk
from hangar.core.retrieval import ScoredChunk


class Retriever(Protocol):
    """
    Finds the chunks that best match a question.

    Attributes:
        id: The retriever's ID, such as ``dense``, written in each result.
    """

    id: str

    def retrieve(self, question: str) -> list[ScoredChunk]:
        """
        Find the chunks for a question.

        Args:
            question: The question, in plain words.

        Returns:
            The chunks found, best first, ranked from 1.
        """
        ...


class FixedRetriever:
    """
    Returns the same chunks for every question. For tests.

    The generation tests of M4 use it, so they can check what is done with
    the chunks without an embedder or an index.

    Attributes:
        id: Always ``fixed``.
    """

    def __init__(self, chunks: Sequence[Chunk]) -> None:
        """
        Set up the retriever.

        Args:
            chunks: The chunks to return, in order.
        """
        self.id = "fixed"
        self._chunks = list(chunks)

    def retrieve(self, question: str) -> list[ScoredChunk]:
        """
        Return the fixed chunks, whatever the question.

        Args:
            question: The question, which is ignored.

        Returns:
            The chunks in their order, ranked from 1, with a score of
            1 / rank.
        """
        return [
            ScoredChunk(chunk=chunk, score=1 / rank, rank=rank, retriever_id=self.id)
            for rank, chunk in enumerate(self._chunks, start=1)
        ]
