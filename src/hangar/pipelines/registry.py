"""
Turning the pipeline configuration into the objects that do the work.

Only this module constructs the adapters, so swapping one, such as the
Docling parser of v2, touches one entry here and one configuration file.
"""

from hangar.chunking.chunker import Chunker
from hangar.chunking.fixed import FixedTokenChunker
from hangar.chunking.hf_tokenizer import HfTokenCounter
from hangar.core.config import (
    ChunkingConfig,
    EmbeddingConfig,
    IndexConfig,
    ParsingConfig,
)
from hangar.core.corpus import DocumentFormat
from hangar.embedding.embedder import Embedder
from hangar.indexing.index import VectorIndex
from hangar.parsing.car import CarXmlParser
from hangar.parsing.parser import Parser
from hangar.parsing.pdf import PdfPageParser
from hangar.parsing.tc_html import TcHtmlParser


def build_parsers(config: ParsingConfig) -> dict[DocumentFormat, Parser]:
    """
    Build one parser per document format.

    Args:
        config: The parsing section of the pipeline configuration.

    Returns:
        The parser for PDF, XML and HTML files.
    """
    return {
        "pdf": PdfPageParser(config.normalisation),
        "xml": CarXmlParser(config.normalisation, config.car.subparts),
        "html": TcHtmlParser(config.normalisation, config.tc_html.content_selectors),
    }


def build_chunker(chunking: ChunkingConfig, embedding: EmbeddingConfig) -> Chunker:
    """
    Build the chunker, with the embedder's tokenizer to count its tokens.

    The tokenizer is downloaded at the pinned revision the first time, then
    read from the Hugging Face cache.

    Args:
        chunking: The chunking section of the pipeline configuration.
        embedding: The embedding section, which names the model whose
            tokenizer counts the tokens.

    Returns:
        The fixed-token chunker.
    """
    counter = HfTokenCounter.from_hub(embedding.model, embedding.revision)

    return FixedTokenChunker(counter, chunking)


def build_embedder(config: EmbeddingConfig, device: str) -> Embedder:
    """
    Build the embedder, loading its model at the pinned revision.

    The model is downloaded the first time, then read from the Hugging Face
    cache.

    Args:
        config: The embedding section of the pipeline configuration.
        device: Where the model runs, from the environment settings.

    Returns:
        The sentence-transformers embedder.
    """
    # Imported here, not at the top: sentence-transformers loads torch,
    # which takes seconds, and only the commands that embed need it.
    from hangar.embedding.st_embedder import SentenceTransformerEmbedder

    return SentenceTransformerEmbedder(config, device)


def build_index(config: IndexConfig, url: str, name: str) -> VectorIndex:
    """
    Build the vector index for one collection on the Qdrant server.

    Args:
        config: The index section of the pipeline configuration.
        url: The Qdrant server, from the environment settings.
        name: The collection name.

    Returns:
        The Qdrant index. It compares vectors with cosine distance, the
        only distance ``config.distance`` accepts in v0.
    """
    # Imported here, not at the top: qdrant-client takes half a second to
    # import, and only the commands that use the index need it.
    from qdrant_client import QdrantClient

    from hangar.indexing.qdrant import QdrantIndex

    return QdrantIndex(QdrantClient(url=url), name)
