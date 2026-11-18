"""
The dense retriever: the question's vector, searched in the vector index.
"""

from hangar.core.retrieval import ScoredChunk
from hangar.embedding.embedder import Embedder
from hangar.indexing.index import VectorIndex


class DenseRetriever:
    """
    Embeds the question and returns the chunks with the closest vectors.

    Attributes:
        id: Always ``dense``.
    """

    def __init__(self, embedder: Embedder, index: VectorIndex, top_k: int) -> None:
        """
        Set up the retriever.

        Args:
            embedder: The embedder that made the chunk vectors; it must
                embed the question the same way.
            index: The vector index that holds the chunks.
            top_k: How many chunks to return, ``retrieval.top_k`` in the
                configuration.
        """
        self.id = "dense"
        self._embedder = embedder
        self._index = index
        self._top_k = top_k

    def retrieve(self, question: str) -> list[ScoredChunk]:
        """
        Find the chunks whose vectors are closest to the question's.

        Args:
            question: The question, in plain words.

        Returns:
            At most ``top_k`` chunks, best first, ranked from 1. Each score
            is the cosine similarity of the question and chunk vectors.
        """
        vector = self._embedder.embed_query(question)
        hits = self._index.search(vector, self._top_k)

        return [
            ScoredChunk(
                chunk=hit.chunk, score=hit.score, rank=rank, retriever_id=self.id
            )
            for rank, hit in enumerate(hits, start=1)
        ]
