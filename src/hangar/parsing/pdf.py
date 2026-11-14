"""
Parsing the FAA handbooks page by page with pypdfium2.

Each PDF page becomes one passage, located by its 1-based index in the file
and by its printed label when the PDF has page labels. v0 keeps the text as
PDFium extracts it: no header removal and no table handling.
"""

import unicodedata
from collections.abc import Sequence
from pathlib import Path

import pypdfium2 as pdfium

from hangar.core.config import NormalisationConfig
from hangar.core.corpus import DocumentSpec
from hangar.core.parsed import (
    PageLocation,
    ParsedDocument,
    ParserInfo,
    ParseWarning,
    Passage,
)
from hangar.files import file_sha256
from hangar.parsing.assemble import TextPart, assemble
from hangar.parsing.parser import ParseError

PARSER_NAME = "pypdfium2"

# PDFium reports a hyphen where it joins a word across a line break as this
# non-character, as in "self\ufffesustaining". The printed page shows a
# hyphen, so the text keeps one.
PDFIUM_HYPHEN = "\ufffe"

# Unicode categories of characters that carry no readable text: control
# characters, private-use characters, surrogates and unassigned code points.
# The replacement character marks text that was lost too.
UNREADABLE_CATEGORIES = frozenset({"Cc", "Co", "Cs", "Cn"})
READABLE_CONTROLS = frozenset("\n\t")
REPLACEMENT_CHARACTER = "\ufffd"


class PdfPageParser:
    """
    Turns a PDF into one passage per page.
    """

    def __init__(self, normalisation: NormalisationConfig) -> None:
        """
        Create the parser.

        Args:
            normalisation: The clean-up applied to the text of each page.
        """
        self._normalisation = normalisation

    def parse(self, document: DocumentSpec, path: Path) -> ParsedDocument:
        """
        Parse one PDF.

        Args:
            document: The manifest entry of the document.
            path: The downloaded PDF. It is read, never changed.

        Returns:
            The canonical text, one passage per page, and a warning for each
            empty or garbled page.

        Raises:
            ParseError: If the file can't be opened as a PDF.
        """
        try:
            parts = read_pages(path)
        except pdfium.PdfiumError as error:
            message = f"{document.id}: can't read {path} as a PDF: {error}"

            raise ParseError(message) from error

        text, passages = assemble(document.id, parts, self._normalisation)

        return ParsedDocument(
            document_id=document.id,
            source_sha256=file_sha256(path),
            parser=ParserInfo(name=PARSER_NAME, version=library_version()),
            text=text,
            passages=passages,
            warnings=page_warnings(text, passages),
        )


def read_pages(path: Path) -> list[TextPart]:
    """
    Extract the text and the location of every page of a PDF.

    Args:
        path: The PDF.

    Returns:
        One part per page, in page order.

    Raises:
        pypdfium2.PdfiumError: If PDFium can't open the file.
    """
    pdf = pdfium.PdfDocument(path)

    try:
        return [_read_page(pdf, index) for index in range(len(pdf))]
    finally:
        pdf.close()


def _read_page(pdf: pdfium.PdfDocument, index: int) -> TextPart:
    """
    Extract the text and location of one page.

    Args:
        pdf: The open PDF.
        index: The 0-based position of the page, as PDFium counts.

    Returns:
        The page's part, with its 1-based index and its label, if any.
    """
    text = str(pdf[index].get_textpage().get_text_range())
    label = str(pdf.get_page_label(index)) or None
    location = PageLocation(page_index=index + 1, page_label=label)

    return TextPart(location, text.replace(PDFIUM_HYPHEN, "-"))


def page_warnings(text: str, passages: Sequence[Passage]) -> tuple[ParseWarning, ...]:
    """
    Find the pages whose text was lost: empty pages and garbled pages.

    A garbled page has characters that carry no readable text, such as the
    control characters PDFium returns for a font it can't map to Unicode.

    Args:
        text: The canonical text.
        passages: The page passages that cover it.

    Returns:
        One warning per empty or garbled page, in page order.
    """
    warnings = []

    for passage in passages:
        page = text[passage.start : passage.end]
        unreadable = sum(1 for char in page if _is_unreadable(char))

        if not page:
            warnings.append(
                ParseWarning(
                    code="empty_page",
                    passage_id=passage.id,
                    message=f"{_describe(passage)} has no text",
                )
            )
        elif unreadable:
            noun = "character" if unreadable == 1 else "characters"
            warnings.append(
                ParseWarning(
                    code="garbled_page",
                    passage_id=passage.id,
                    message=f"{_describe(passage)} has {unreadable} unreadable {noun}",
                )
            )

    return tuple(warnings)


def library_version() -> str:
    """
    Name the versions of pypdfium2 and of the PDFium build it bundles.

    Returns:
        A version such as ``5.15.2 (PDFium 8149)``.
    """
    pypdfium = pdfium.version.PYPDFIUM_INFO.version
    build = pdfium.version.PDFIUM_INFO.build

    return f"{pypdfium} (PDFium {build})"


def _is_unreadable(char: str) -> bool:
    return (
        char not in READABLE_CONTROLS
        and unicodedata.category(char) in UNREADABLE_CATEGORIES
    ) or char == REPLACEMENT_CHARACTER


def _describe(passage: Passage) -> str:
    location = passage.location

    if not isinstance(location, PageLocation):
        return passage.id

    page = f"page {location.page_index}"

    return f"{page} (printed {location.page_label})" if location.page_label else page
