"""
The index manifest: what a Qdrant collection holds and where it came from.

``hangar index`` writes it to ``results/<run name>/index-manifest.json``,
which is committed. The collection lives in a Docker volume that can be
wiped at any time; the manifest says what rebuilding it must give.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from hangar.core.chunks import Sha256
from hangar.core.vectors import EmbedderInfo


class IndexManifest(BaseModel):
    """
    The record of one built collection.

    It holds only values that change with the collection: no time, run ID or
    commit, so rebuilding from the same inputs writes the same file. The
    time of a build is in the run's log.

    Attributes:
        collection: The collection name, such as
            ``c1__fixed512__bge-m3-dense``.
        snapshot: The corpus snapshot, such as ``c1``.
        chunker_id: The chunker, such as ``fixed512``.
        embedder_id: The embedder, such as ``bge-m3-dense``.
        embedder: The model, its revision, its dimension and whether its
            vectors are normalised.
        distance: How Qdrant compares vectors.
        points: How many points the collection holds, one per chunk.
        qdrant_version: The version of the Qdrant server.
        config_hash: The hash of the pipeline configuration of the run.
        chunks_sha256: The SHA-256 of the ``chunks.jsonl`` file that was
            read.
        vectors_sha256: The SHA-256 of the ``vectors.parquet`` file that
            was read.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    collection: str = Field(min_length=1)
    snapshot: str = Field(min_length=1)
    chunker_id: str = Field(min_length=1)
    embedder_id: str = Field(min_length=1)
    embedder: EmbedderInfo
    distance: Literal["cosine"]
    points: PositiveInt
    qdrant_version: str = Field(min_length=1)
    config_hash: Sha256
    chunks_sha256: Sha256
    vectors_sha256: Sha256
