"""
The vector index on Qdrant.

Real runs use the Qdrant server from Docker Compose; tests use the client's
in-memory mode, ``QdrantClient(":memory:")``, through the same calls.
"""

from collections.abc import Mapping, Sequence

from qdrant_client import QdrantClient, models

from hangar.core.chunks import Chunk
from hangar.indexing.index import IndexHit, VectorIndexError

# Points are sent this many at a time, so one request stays a few megabytes
# even with the chunks' text in the payload.
UPSERT_BATCH = 256


class QdrantIndex:
    """
    Stores chunk vectors in one Qdrant collection, with cosine distance.

    A point's ID is its chunk ID read as a 64-bit number, so the same chunk
    always lands on the same point. Its payload is the whole chunk.

    Attributes:
        name: The collection name.
    """

    def __init__(self, client: QdrantClient, name: str) -> None:
        """
        Set up the index.

        Args:
            client: The Qdrant client, for a server or in memory.
            name: The collection name, such as ``c1__fixed512__bge-m3-dense``.
        """
        self.name = name
        self._client = client

    def recreate(self, dimension: int) -> None:
        """
        Delete the collection if it exists, then create it empty.

        Args:
            dimension: How many values each vector has.
        """
        if self._client.collection_exists(self.name):
            self._client.delete_collection(self.name)

        self._client.create_collection(
            self.name,
            vectors_config=models.VectorParams(
                size=dimension, distance=models.Distance.COSINE
            ),
        )

    def check(self, dimension: int) -> None:
        """
        Check that the collection exists and holds vectors of a dimension.

        Args:
            dimension: How many values each vector should have.

        Raises:
            VectorIndexError: If the collection is missing or holds vectors
                of another dimension.
        """
        if not self._client.collection_exists(self.name):
            raise VectorIndexError(
                f"{self.name}: the collection doesn't exist; run hangar index first"
            )

        params = self._client.get_collection(self.name).config.params.vectors
        # A collection with named vectors has a mapping here instead, which
        # v0 never creates.
        size = params.size if isinstance(params, models.VectorParams) else None

        if size != dimension:
            raise VectorIndexError(
                f"{self.name}: the collection holds vectors of {size} values, "
                f"not {dimension}"
            )

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
        if len(chunks) != len(vectors):
            raise VectorIndexError(
                f"{self.name}: {len(chunks)} chunks but {len(vectors)} vectors"
            )

        points = [
            models.PointStruct(
                id=int(chunk.id, 16),
                vector=list(vector),
                payload=chunk.model_dump(mode="json"),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]

        for start in range(0, len(points), UPSERT_BATCH):
            self._client.upsert(
                self.name, points[start : start + UPSERT_BATCH], wait=True
            )

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
        query_filter = None

        if filters:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(key=key, match=models.MatchValue(value=value))
                    for key, value in filters.items()
                ]
            )

        points = self._client.query_points(
            self.name,
            query=list(vector),
            limit=k,
            query_filter=query_filter,
            with_payload=True,
        ).points

        return [
            IndexHit(chunk=Chunk.model_validate(point.payload), score=point.score)
            for point in points
        ]

    def count(self) -> int:
        """
        Count the points in the collection.

        Returns:
            The exact number of points.
        """
        return self._client.count(self.name, exact=True).count

    def version(self) -> str:
        """
        Name the Qdrant version, for the index manifest.

        Returns:
            The server's version, such as ``1.20.0``. In memory, the
            client's version.
        """
        return self._client.info().version
