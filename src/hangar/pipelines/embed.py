"""The embed pipeline: from a chunks file to one vector per chunk."""

import logging
import time
from pathlib import Path

from hangar.core.chunks import chunker_id
from hangar.core.config import PipelineConfig, config_hash
from hangar.core.vectors import EmbedderInfo, VectorRecord, VectorsMeta, embedder_id
from hangar.embedding.embedder import Embedder, EmbedError
from hangar.files import file_sha256, replace_folder, write_text
from hangar.pipelines.chunk_file import read_chunks
from hangar.pipelines.provenance import code_version
from hangar.pipelines.registry import build_embedder
from hangar.pipelines.settings import Settings
from hangar.pipelines.vector_file import write_vectors

logger = logging.getLogger(__name__)

# Chunks go to the embedder this many batches at a time, with a progress
# line after each group: about 12 lines for C1.
BATCHES_PER_LOG = 20


def run_embed(
    settings: Settings, config: PipelineConfig, embedder: Embedder | None = None
) -> VectorsMeta:
    """
    Embed every chunk of the configured snapshot and chunker.

    The stage reads only the chunks file, so it can run on another machine,
    such as a notebook GPU, and hand back the vectors folder. The vectors and
    their ``meta.json`` replace the folder whole, so it never mixes two runs.

    Args:
        settings: Where Hangar runs, and the device the model runs on.
            Chunks are read from
            ``<data folder>/chunks/<snapshot>/<chunker ID>/chunks.jsonl``,
            and vectors are written to
            ``<data folder>/vectors/<snapshot>/<chunker ID>/<embedder ID>/``.
        config: The pipeline configuration: the snapshot, the chunker and
            the embedder.
        embedder: The embedder to use instead of the configured one, for
            tests.

    Returns:
        What the run wrote: its input, its embedder and its count.

    Raises:
        ChunkError: If the chunks file lists a chunk twice.
        EmbedError: If the chunks file is missing, or the embedder returns
            too few vectors or vectors of the wrong dimension.
    """
    snapshot, chunker = config.corpus.snapshot, chunker_id(config.chunking)
    chunks_path = settings.data_dir / "chunks" / snapshot / chunker / "chunks.jsonl"

    if not chunks_path.is_file():
        raise EmbedError(
            f"{snapshot}/{chunker}: {chunks_path} is missing; run hangar chunk first"
        )

    chunks = read_chunks(chunks_path)
    logger.info("read %s: %d chunks", chunks_path, len(chunks))
    logger.info("code at %s", code_version(Path.cwd()))

    embedder = embedder or build_embedder(config.embedding, settings.device)
    logger.info(
        "embedding with %s at revision %s on %s",
        embedder.model_id,
        embedder.revision,
        settings.device,
    )
    vectors = _embed(embedder, [c.text for c in chunks], config.embedding.batch_size)

    if len(vectors) != len(chunks):
        raise EmbedError(
            f"{snapshot}/{chunker}: the embedder returned {len(vectors)} vectors "
            f"for {len(chunks)} chunks"
        )

    records = [
        VectorRecord(
            chunk_id=chunk.id,
            model_id=embedder.model_id,
            revision=embedder.revision,
            vector=tuple(vector),
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    meta = VectorsMeta(
        snapshot=snapshot,
        chunker_id=chunker,
        embedder_id=embedder_id(config.embedding),
        config_hash=config_hash(config),
        embedder=EmbedderInfo(
            model_id=embedder.model_id,
            revision=embedder.revision,
            dimension=embedder.dimension,
            normalized=embedder.normalized,
        ),
        chunks_sha256=file_sha256(chunks_path),
        vectors=len(records),
    )
    vectors_dir = settings.data_dir / "vectors" / snapshot / chunker / meta.embedder_id

    with replace_folder(vectors_dir) as partial:
        write_vectors(partial / "vectors.parquet", records, embedder.dimension)
        write_text(partial / "meta.json", meta.model_dump_json(indent=2))

    logger.info("wrote %s: %d vectors", vectors_dir, meta.vectors)

    return meta


def _embed(embedder: Embedder, texts: list[str], batch_size: int) -> list[list[float]]:
    group = batch_size * BATCHES_PER_LOG
    started = time.monotonic()
    vectors: list[list[float]] = []

    for start in range(0, len(texts), group):
        vectors.extend(embedder.embed_documents(texts[start : start + group]))
        logger.info(
            "embedded %d of %d chunks in %.0f s",
            min(start + group, len(texts)),
            len(texts),
            time.monotonic() - started,
        )

    return vectors
