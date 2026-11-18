"""The index pipeline: from the chunks and their vectors to a Qdrant collection."""

import logging
import time
from pathlib import Path

from hangar.core.chunks import Chunk, chunker_id
from hangar.core.config import PipelineConfig, config_hash
from hangar.core.vectors import VectorRecord, VectorsMeta, embedder_id
from hangar.files import file_sha256, write_text
from hangar.indexing.index import VectorIndex, VectorIndexError
from hangar.indexing.manifest import IndexManifest
from hangar.indexing.naming import collection_name
from hangar.pipelines.chunk_file import read_chunks
from hangar.pipelines.provenance import code_version
from hangar.pipelines.registry import build_index
from hangar.pipelines.settings import Settings
from hangar.pipelines.vector_file import read_vectors

logger = logging.getLogger(__name__)


def run_index(
    settings: Settings,
    config: PipelineConfig,
    results_dir: Path = Path("results"),
    index: VectorIndex | None = None,
) -> IndexManifest:
    """
    Build the collection of the configured snapshot, chunker and embedder.

    The collection is deleted and built again on every run, so it holds
    exactly the current chunks, with no point left from an earlier parse
    (ADR-0008).

    Args:
        settings: Where Hangar runs, and the Qdrant server. Chunks are read
            from ``<data folder>/chunks/<snapshot>/<chunker ID>/`` and
            vectors from ``<data folder>/vectors/<snapshot>/<chunker ID>/
            <embedder ID>/``.
        config: The pipeline configuration: the snapshot, the chunker, the
            embedder and the index.
        results_dir: The folder of committed results. The manifest goes to
            ``<results_dir>/<run name>/index-manifest.json``.
        index: The vector index to use instead of the configured one, for
            tests.

    Returns:
        The index manifest.

    Raises:
        ChunkError: If the chunks file lists a chunk twice.
        VectorIndexError: If the chunks or vectors are missing, the vectors
            were made from another chunks file, chunks and vectors don't
            match one to one, or the collection ends with another number of
            points.
    """
    snapshot = config.corpus.snapshot
    chunker, embedder = chunker_id(config.chunking), embedder_id(config.embedding)
    name = collection_name(snapshot, chunker, embedder)
    chunks_path = settings.data_dir / "chunks" / snapshot / chunker / "chunks.jsonl"
    vectors_dir = settings.data_dir / "vectors" / snapshot / chunker / embedder

    _require(name, chunks_path, "hangar chunk")
    _require(name, vectors_dir / "vectors.parquet", "hangar embed")
    logger.info("code at %s", code_version(Path.cwd()))

    chunks = read_chunks(chunks_path)
    meta = VectorsMeta.model_validate_json(
        (vectors_dir / "meta.json").read_text(encoding="utf-8")
    )
    chunks_sha256 = file_sha256(chunks_path)

    if meta.chunks_sha256 != chunks_sha256:
        raise VectorIndexError(
            f"{name}: the vectors in {vectors_dir} were made from another chunks "
            "file; run hangar embed again"
        )

    vectors = _vectors_in_chunk_order(
        name, chunks, read_vectors(vectors_dir / "vectors.parquet")
    )
    logger.info("read %d chunks and their vectors", len(chunks))

    index = index or build_index(config.index, str(settings.qdrant_url), name)
    started = time.monotonic()
    index.recreate(meta.embedder.dimension)
    index.upsert(chunks, vectors)
    points = index.count()

    if points != len(chunks):
        raise VectorIndexError(f"{name}: {points} points for {len(chunks)} chunks")

    logger.info(
        "built collection %s: %d points in %.1f s",
        name,
        points,
        time.monotonic() - started,
    )

    manifest = IndexManifest(
        collection=name,
        snapshot=snapshot,
        chunker_id=chunker,
        embedder_id=embedder,
        embedder=meta.embedder,
        distance=config.index.distance,
        points=points,
        qdrant_version=index.version(),
        config_hash=config_hash(config),
        chunks_sha256=chunks_sha256,
        vectors_sha256=file_sha256(vectors_dir / "vectors.parquet"),
    )
    manifest_path = results_dir / config.run.name / "index-manifest.json"
    write_text(manifest_path, manifest.model_dump_json(indent=2))
    logger.info("wrote %s", manifest_path)

    return manifest


def _require(name: str, path: Path, command: str) -> None:
    if not path.is_file():
        raise VectorIndexError(f"{name}: {path} is missing; run {command} first")


def _vectors_in_chunk_order(
    name: str, chunks: list[Chunk], records: list[VectorRecord]
) -> list[tuple[float, ...]]:
    # Every chunk must have exactly one vector, and every vector a chunk.
    if len(records) != len(chunks):
        raise VectorIndexError(
            f"{name}: {len(chunks)} chunks but {len(records)} vectors"
        )

    by_id = {record.chunk_id: record.vector for record in records}

    if len(by_id) != len(records):
        raise VectorIndexError(f"{name}: a chunk has more than one vector")

    missing = [chunk.id for chunk in chunks if chunk.id not in by_id]

    if missing:
        raise VectorIndexError(
            f"{name}: {len(missing)} of {len(chunks)} chunks have no vector, "
            f"such as {missing[0]}"
        )

    return [by_id[chunk.id] for chunk in chunks]
