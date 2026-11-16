"""The chunk pipeline: from the parsed folder to one chunk file per chunker."""

import logging
from pathlib import Path

from hangar.chunking.chunker import Chunker, ChunkError
from hangar.core.chunks import Chunk, ChunksMeta, TokenizerInfo
from hangar.core.config import PipelineConfig, config_hash
from hangar.core.parsed import ParsedFile
from hangar.files import file_sha256, replace_folder, write_text
from hangar.observability.logs import log_context
from hangar.pipelines.provenance import code_version
from hangar.pipelines.registry import build_chunker
from hangar.pipelines.settings import Settings

logger = logging.getLogger(__name__)


def run_chunk(
    settings: Settings, config: PipelineConfig, chunker: Chunker | None = None
) -> ChunksMeta:
    """
    Split every parsed document of the configured snapshot into chunks.

    The chunks and their ``meta.json`` replace the chunker's folder whole,
    so it never mixes two runs.

    Args:
        settings: Where Hangar runs. Parsed files are read from
            ``<data folder>/parsed/<snapshot>/``, and chunks are written to
            ``<data folder>/chunks/<snapshot>/<chunker ID>/chunks.jsonl``.
        config: The pipeline configuration: the snapshot, the chunker and
            the embedder whose tokenizer counts the tokens.
        chunker: The chunker to use instead of the configured one, for
            tests.

    Returns:
        What the run wrote: its inputs, its tokenizer and its counts.

    Raises:
        ChunkError: If there are no parsed files, or a document can't be
            chunked.
    """
    snapshot = config.corpus.snapshot
    parsed_dir = settings.data_dir / "parsed" / snapshot
    paths = sorted(parsed_dir.glob("*.json"))

    if not paths:
        raise ChunkError(
            f"{snapshot}: {parsed_dir} has no parsed files; run hangar parse first"
        )

    logger.info("read %s: %d parsed files", parsed_dir, len(paths))
    logger.info("code at %s", code_version(Path.cwd()))

    chunker = chunker or build_chunker(config.chunking, config.embedding)
    chunks = [chunk for path in paths for chunk in _chunk_file(path, chunker)]

    meta = ChunksMeta(
        snapshot=snapshot,
        chunker_id=chunker.id,
        config_hash=config_hash(config),
        tokenizer=TokenizerInfo(
            model=config.embedding.model, revision=config.embedding.revision
        ),
        parsed_files={path.stem: file_sha256(path) for path in paths},
        chunks=len(chunks),
        tokens=sum(chunk.token_count for chunk in chunks),
    )
    chunks_dir = settings.data_dir / "chunks" / snapshot / chunker.id

    with replace_folder(chunks_dir) as partial:
        write_text(
            partial / "chunks.jsonl",
            "\n".join(chunk.model_dump_json() for chunk in chunks),
        )
        write_text(partial / "meta.json", meta.model_dump_json(indent=2))

    logger.info(
        "wrote %s: %d chunks from %d documents, %d tokens",
        chunks_dir,
        meta.chunks,
        meta.documents,
        meta.tokens,
    )

    return meta


def _chunk_file(path: Path, chunker: Chunker) -> list[Chunk]:
    document = ParsedFile.model_validate_json(path.read_text(encoding="utf-8")).document

    with log_context(document_id=document.document_id):
        chunks = chunker.chunk(document)
        logger.info("chunked %s: %d chunks", path, len(chunks))

        return chunks
