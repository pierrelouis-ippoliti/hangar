"""The search pipeline: the chunks for a question, without the language model."""

import logging
from collections.abc import Sequence

from hangar.core.chunks import chunker_id, describe_passages
from hangar.core.config import PipelineConfig
from hangar.core.retrieval import ScoredChunk
from hangar.core.vectors import embedder_id
from hangar.indexing.naming import collection_name
from hangar.pipelines.registry import build_embedder, build_index, build_retriever
from hangar.pipelines.settings import Settings
from hangar.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)

# How much of each chunk's text the results show.
EXCERPT_CHARACTERS = 160


def run_search(
    settings: Settings,
    config: PipelineConfig,
    question: str,
    retriever: Retriever | None = None,
) -> list[ScoredChunk]:
    """
    Find the chunks for a question in the configured collection.

    Args:
        settings: Where Hangar runs: the Qdrant server and the device the
            embedding model runs on.
        config: The pipeline configuration: the collection's snapshot,
            chunker and embedder, and the retriever with its top k.
        question: The question, in plain words.
        retriever: The retriever to use instead of the configured one, for
            tests.

    Returns:
        The chunks found, best first.

    Raises:
        VectorIndexError: If Qdrant can't be reached, or the collection is
            missing or holds vectors of another dimension.
    """
    if retriever is None:
        retriever = _configured_retriever(settings, config)

    results = retriever.retrieve(question)
    logger.info(
        "found %d chunks with the %s retriever: %s",
        len(results),
        retriever.id,
        ", ".join(f"{r.chunk.id} ({r.score:.3f})" for r in results),
    )

    return results


def format_results(results: Sequence[ScoredChunk]) -> str:
    """
    Write search results for the screen, two lines per chunk.

    The first line holds the rank, the score, the document and the pages
    or sections; the second an excerpt of the chunk's text. A blank line
    separates two results.

    Args:
        results: The chunks found, best first.

    Returns:
        The text to print, such as::

            1. 0.712  faa-h-8083-30b, p. 142 (7-12)
               Torque the propeller attaching bolts to the value given…
    """
    if not results:
        return "No chunk found."

    blocks = []

    for result in results:
        chunk = result.chunk
        location = describe_passages(chunk.passages)
        blocks.append(
            f"{result.rank}. {result.score:.3f}  {chunk.document_id}, {location}\n"
            f"   {_excerpt(chunk.text)}"
        )

    return "\n\n".join(blocks)


def _configured_retriever(settings: Settings, config: PipelineConfig) -> Retriever:
    snapshot = config.corpus.snapshot
    name = collection_name(
        snapshot, chunker_id(config.chunking), embedder_id(config.embedding)
    )
    index = build_index(config.index, str(settings.qdrant_url), name)
    embedder = build_embedder(config.embedding, settings.device)
    index.check(embedder.dimension)

    return build_retriever(config.retrieval, embedder, index)


def _excerpt(text: str) -> str:
    flat = " ".join(text.split())

    if len(flat) <= EXCERPT_CHARACTERS:
        return flat

    return flat[:EXCERPT_CHARACTERS] + "…"
