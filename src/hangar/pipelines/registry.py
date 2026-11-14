"""
Turning the pipeline configuration into the objects that do the work.

Only this module constructs the adapters, so swapping one, such as the
Docling parser of v2, touches one entry here and one configuration file.
"""

from hangar.core.config import ParsingConfig
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
