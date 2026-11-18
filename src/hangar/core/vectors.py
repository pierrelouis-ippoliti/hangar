"""
Vectors: what the embed stage writes for each chunk.

The embed stage turns each chunk's text into one vector. A vector set is
named by the snapshot, the chunker and the embedder, such as
``c1/fixed512/bge-m3-dense``, so vectors from two models or two chunkers
never mix.
"""

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from hangar.core.chunks import CHUNK_ID_LENGTH, Sha256
from hangar.core.config import EmbeddingConfig


class VectorModel(BaseModel):
    """
    A part of a vector set: frozen, and with no unknown fields.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


def embedder_id(config: EmbeddingConfig) -> str:
    """
    Name an embedder configuration, for folders and collections.

    Args:
        config: The embedding section of the pipeline configuration.

    Returns:
        The model name without its organisation, in lower case, followed by
        the output used, such as ``bge-m3-dense`` for ``BAAI/bge-m3``.
    """
    name = config.model.rsplit("/", 1)[-1].lower()

    return f"{name}-{config.output}"


class VectorRecord(VectorModel):
    """
    One chunk's vector, with the model that made it.

    Attributes:
        chunk_id: The ID of the chunk the vector stands for.
        model_id: The model that made the vector, such as ``BAAI/bge-m3``.
        revision: The model's revision, such as its commit hash.
        vector: The vector's values.
    """

    chunk_id: str = Field(pattern=rf"^[0-9a-f]{{{CHUNK_ID_LENGTH}}}$")
    model_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    vector: tuple[float, ...] = Field(min_length=1)


class EmbedderInfo(VectorModel):
    """
    The embedder that made a vector set.

    Attributes:
        model_id: The model, such as ``BAAI/bge-m3``.
        revision: The model's revision, such as its commit hash.
        dimension: How many values each vector has.
        normalized: Whether the vectors have unit length.
    """

    model_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    dimension: PositiveInt
    normalized: bool


class VectorsMeta(VectorModel):
    """
    Where a vector set came from: the ``meta.json`` next to the vectors.

    Like the chunks' ``meta.json``, it holds no time, run ID or commit, so
    two runs with the same inputs write the same file.

    Attributes:
        snapshot: The corpus snapshot, such as ``c1``.
        chunker_id: The chunker of the chunks, such as ``fixed512``.
        embedder_id: The embedder, such as ``bge-m3-dense``.
        config_hash: The hash of the pipeline configuration of the run.
        embedder: The model, its revision, its dimension and whether its
            vectors are normalised.
        chunks_sha256: The SHA-256 of the ``chunks.jsonl`` file that was
            read.
        vectors: How many vectors were written, one per chunk.
    """

    snapshot: str = Field(min_length=1)
    chunker_id: str = Field(min_length=1)
    embedder_id: str = Field(min_length=1)
    config_hash: Sha256
    embedder: EmbedderInfo
    chunks_sha256: Sha256
    vectors: PositiveInt
