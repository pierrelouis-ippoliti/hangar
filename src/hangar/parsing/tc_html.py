"""
Parsing Transport Canada's standards and advisory circulars from their pages.

The content of a page is the element its content selector picks, an XPath
expression from the pipeline file (``//main`` for every C1 page). Inside it,
a heading from ``h2`` to ``h6`` whose text starts with a section number, such
as ``571.10`` or ``4.1.1``, starts a passage. Heading levels differ from page
to page, so the number decides, not the level. Unnumbered headings stay in
the section before them, and the text before the first numbered section is
a front-matter passage.
"""

import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from lxml import etree, html

from hangar.core.config import ContentSelectors, NormalisationConfig
from hangar.core.corpus import DocumentSpec
from hangar.core.parsed import (
    ParsedDocument,
    ParserInfo,
    ParseWarning,
    SectionLocation,
    passage_id,
)
from hangar.files import file_sha256
from hangar.parsing.assemble import TextPart, assemble
from hangar.parsing.lxml_version import lxml_version
from hangar.parsing.parser import ParseError

PARSER_NAME = "tc-html"

# A section number has at least two parts and is followed by a space or
# nothing: "1.0 Introduction", "571.10", "4.1.1 General".
SECTION_NUMBER = re.compile(r"^(\d+(?:\.\d+)+)(?=\s|$)")
SECTION_HEADING_LEVELS = {"h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}

# Elements whose content starts and ends a line of text.
BLOCK_TAGS = frozenset(
    {
        "address", "article", "aside", "blockquote", "caption", "dd", "details",
        "div", "dl", "dt", "figcaption", "figure", "footer", "form", "h1", "h2",
        "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p",
        "pre", "section", "summary", "table", "tbody", "tfoot", "thead", "tr",
        "ul",
    }
)  # fmt: skip
CELL_TAGS = frozenset({"td", "th"})
# Elements that hold no page text.
SKIPPED_TAGS = frozenset({"script", "style", "noscript", "template"})


class TcHtmlParser:
    """
    Turns a Transport Canada page into front matter and numbered sections.
    """

    def __init__(
        self, normalisation: NormalisationConfig, selectors: ContentSelectors
    ) -> None:
        """
        Create the parser.

        Args:
            normalisation: The clean-up applied to the text of each passage.
            selectors: The XPath expression that picks the content of each
                type of page.
        """
        self._normalisation = normalisation
        self._selectors = selectors

    def parse(self, document: DocumentSpec, path: Path) -> ParsedDocument:
        """
        Parse one page.

        Args:
            document: The manifest entry of the standard or circular.
            path: The downloaded page. It is read, never changed.

        Returns:
            The canonical text, with a front-matter passage first, then one
            passage per numbered section. A page with no numbered section
            gets a ``no_sections`` warning.

        Raises:
            ParseError: If the page can't be read, its document type has no
                selector, the selector doesn't pick exactly one element, or
                two sections have the same number.
        """
        content = _select_content(document, path, self._selector(document))
        parts = section_parts(content)
        _check_unique_labels(document, parts)
        text, passages = assemble(document.id, parts, self._normalisation)

        return ParsedDocument(
            document_id=document.id,
            source_sha256=file_sha256(path),
            parser=ParserInfo(name=PARSER_NAME, version=lxml_version()),
            text=text,
            passages=passages,
            warnings=_no_sections_warning(document, parts),
        )

    def _selector(self, document: DocumentSpec) -> str:
        if document.type == "standard":
            return self._selectors.standard

        if document.type == "advisory_circular":
            return self._selectors.advisory_circular

        raise ParseError(
            f"{document.id}: no content selector for documents of type {document.type}"
        )


def section_parts(content: html.HtmlElement) -> list[TextPart]:
    """
    Cut a page's content into a front-matter part and one part per section.

    Args:
        content: The element the content selector picked.

    Returns:
        The front matter first, then the sections, in page order.
    """
    splitter = _SectionSplitter(_title(content))
    splitter.walk(content)

    return splitter.parts()


class _SectionSplitter:
    """
    Writes the content's text into parts, one per section.

    It walks the content in page order, writing into the current part, and
    starts a new part at each numbered heading.
    """

    def __init__(self, title: str | None) -> None:
        self._title_path = (title,) if title else ()
        self._numbered: dict[int, str] = {}
        front = SectionLocation(label=None, heading_path=self._title_path)
        self._parts: list[tuple[SectionLocation, list[str]]] = [(front, [])]

    def walk(self, element: html.HtmlElement) -> None:
        tag = element.tag

        if tag in SKIPPED_TAGS:
            return

        if tag in SECTION_HEADING_LEVELS:
            self._start_section_at(element)

        if tag in BLOCK_TAGS or tag == "br":
            self._write_newline()
        elif tag in CELL_TAGS:
            self._write(" ")

        self._write(element.text)

        for child in element:
            # Comments and processing instructions hold no page text, but
            # the text after them does.
            if isinstance(child.tag, str):
                self.walk(child)

            self._write(child.tail)

        if tag in BLOCK_TAGS:
            self._write_newline()

    def parts(self) -> list[TextPart]:
        return [
            TextPart(location, _lines("".join(pieces)))
            for location, pieces in self._parts
        ]

    def _start_section_at(self, heading: html.HtmlElement) -> None:
        text = _inline_text(heading.itertext())
        match = SECTION_NUMBER.match(text)

        if not match:
            return

        level = SECTION_HEADING_LEVELS[str(heading.tag)]
        self._numbered = {lvl: t for lvl, t in self._numbered.items() if lvl < level}
        self._numbered[level] = text
        path = self._title_path + tuple(t for _, t in sorted(self._numbered.items()))
        location = SectionLocation(label=match.group(1), heading_path=path)
        self._parts.append((location, []))

    def _write(self, text: str | None) -> None:
        # Line breaks and indentation in the HTML source carry no meaning.
        if text:
            self._parts[-1][1].append(re.sub(r"\s+", " ", text))

    def _write_newline(self) -> None:
        self._parts[-1][1].append("\n")


def _select_content(
    document: DocumentSpec, path: Path, selector: str
) -> html.HtmlElement:
    parser = html.HTMLParser(no_network=True)

    try:
        tree = html.parse(str(path), parser)
    except (OSError, etree.LxmlError) as error:
        message = f"{document.id}: can't read {path} as HTML: {error}"

        raise ParseError(message) from error

    if tree.getroot() is None:
        raise ParseError(f"{document.id}: {path} holds no HTML")

    try:
        found = tree.xpath(selector)
    except etree.XPathError as error:
        message = f"{document.id}: invalid content selector {selector!r}: {error}"

        raise ParseError(message) from error

    elements = (
        [item for item in found if isinstance(item, html.HtmlElement)]
        if isinstance(found, list)
        else []
    )

    if len(elements) != 1:
        raise ParseError(
            f"{document.id}: the content selector {selector!r} matches "
            f"{len(elements)} elements in {path}, not one"
        )

    return elements[0]


def _title(content: html.HtmlElement) -> str | None:
    headings = content.xpath(".//h1")

    if isinstance(headings, list) and headings:
        first = headings[0]

        if isinstance(first, html.HtmlElement):
            return _inline_text(first.itertext()) or None

    return None


def _check_unique_labels(document: DocumentSpec, parts: list[TextPart]) -> None:
    labels = Counter(
        part.location.label
        for part in parts
        if isinstance(part.location, SectionLocation) and part.location.label
    )
    repeated = sorted(label for label, count in labels.items() if count > 1)

    if repeated:
        names = ", ".join(repeated)

        raise ParseError(f"{document.id}: more than one section numbered {names}")


def _no_sections_warning(
    document: DocumentSpec, parts: list[TextPart]
) -> tuple[ParseWarning, ...]:
    if len(parts) > 1:
        return ()

    front = parts[0].location

    return (
        ParseWarning(
            code="no_sections",
            passage_id=passage_id(document.id, front),
            message="no numbered section found; the whole page is front matter",
        ),
    )


def _inline_text(pieces: Iterable[str]) -> str:
    return " ".join("".join(pieces).split())


def _lines(text: str) -> str:
    lines = (line.strip() for line in text.split("\n"))

    return "\n".join(line for line in lines if line)
