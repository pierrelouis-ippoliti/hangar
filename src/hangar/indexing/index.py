"""
The vector index interface: what every vector store provides.

v0 stores its vectors in Qdrant. Each point holds one chunk's vector and
the whole chunk as its payload, so a search returns chunks without reading
the chunk files.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from hangar.core.chunks import Chunk
from hangar.core.errors import HangarError


class VectorIndexError(HangarError):
    """
    A collection that is missing or doesn't match, or unstorable vectors.

    The message starts with the collection name.
    """


@dataclass(frozen=True)
class IndexHit:
    """
    One chunk found by a search.

    Attributes:
        chunk: The chunk, read from the point's payload.
        score: How close its vector is to the query vector; with cosine
            distance, 1 for the same direction.
    """

    chunk: Chunk
    score: float


class VectorIndex(Protocol):
    """
    Stores chunk vectors in one collection, and searches them.

    Attributes:
        name: The collection name, such as ``c1__fixed512__bge-m3-dense``.
    """

    name: str

    def recreate(self, dimension: int) -> None:
        """
        Delete the collection if it exists, then create it empty.

        Args:
            dimension: How many values each vector has.
        """
        ...

    def check(self, dimension: int) -> None:
        """
        Check that the collection exists and holds vectors of a dimension.

        Args:
            dimension: How many values each vector should have.

        Raises:
            VectorIndexError: If the collection is missing or holds vectors
                of another dimension.
        """
        ...

    def upsert(
        self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]
    ) -> None:
        """
        Store each chunk with its vector, replacing a point with the same ID.

        Args:
            chunks: The chunks, stored whole as the points' payload.
            vectors: One vector per chunk, in the same order.

        Raises:
            VectorIndexError: If there isn't one vector per chunk.
        """
        ...

    def search(
        self,
        vector: Sequence[float],
        k: int,
        filters: Mapping[str, str | int] | None = None,
    ) -> list[IndexHit]:
        """
        Find the chunks whose vectors are closest to a vector.

        Args:
            vector: The query vector.
            k: The most chunks to return.
            filters: Payload fields and the values they must equal, such as
                ``{"document_id": "tc-std-571"}``, or None for no filter.

        Returns:
            At most k hits, the closest first.
        """
        ...

    def count(self) -> int:
        """
        Count the points in the collection.

        Returns:
            The exact number of points.
        """
        ...

    def version(self) -> str:
        """
        Name the version of the store, for the index manifest.

        Returns:
            The version, such as ``1.20.0``.
        """
        ...
