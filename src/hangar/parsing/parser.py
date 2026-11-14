"""
The parser interface: what every document parser provides.

v0 has one parser per format: PDF pages with pypdfium2, CAR sections from
the Justice Canada XML, and Transport Canada sections from HTML. v2 adds a
Docling parser for PDFs, chosen by configuration, which is why parsers sit
behind this interface.
"""

from pathlib import Path
from typing import Protocol

from hangar.core.corpus import DocumentSpec
from hangar.core.errors import HangarError
from hangar.core.parsed import ParsedDocument


class ParseError(HangarError):
    """
    A file that couldn't be parsed. The message starts with the document ID.
    """


class Parser(Protocol):
    """
    Turns a downloaded file into a parsed document.
    """

    def parse(self, document: DocumentSpec, path: Path) -> ParsedDocument:
        """
        Parse one downloaded file.

        Args:
            document: The manifest entry of the document.
            path: The downloaded file. It is read, never changed.

        Returns:
            The canonical text, passages that cover it exactly once, and any
            warnings, such as empty pages.

        Raises:
            ParseError: If the file can't be read as its format.
        """
        ...
