"""
Turning the pipeline configuration into the objects that do the work.

Only this module constructs the adapters, so swapping one, such as the
Docling parser of v2, touches one entry here and one configuration file.
"""

from hangar.chunking.chunker import Chunker
from hangar.chunking.fixed import FixedTokenChunker
from hangar.chunking.hf_tokenizer import HfTokenCounter
from hangar.core.config import ChunkingConfig, EmbeddingConfig, ParsingConfig
from hangar.core.corpus import DocumentFormat
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
