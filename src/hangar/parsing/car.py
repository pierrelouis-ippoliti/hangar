"""
Parsing the Canadian Aviation Regulations from the Justice Canada XML.

Only the sections of the configured subparts are kept, 571 and 573 in v0,
each as one passage labelled like ``571.10``. In this XML, headings don't
wrap their sections: ``Heading`` elements with a ``level`` from 1 to 5 sit
next to the ``Section`` elements under ``Body``. A section's heading path is
therefore the latest heading at each level before it.
"""

from collections.abc import Sequence
from pathlib import Path

from lxml import etree

from hangar.core.config import NormalisationConfig
from hangar.core.corpus import DocumentSpec
from hangar.core.parsed import ParsedDocument, ParserInfo, SectionLocation
from hangar.files import file_sha256
from hangar.parsing.assemble import TextPart, assemble
from hangar.parsing.parser import ParseError

PARSER_NAME = "car-xml"


class CarXmlParser:
    """
    Turns the regulation XML into one passage per section of the kept subparts.
    """

    def __init__(
        self, normalisation: NormalisationConfig, subparts: Sequence[str]
    ) -> None:
        """
        Create the parser.

        Args:
            normalisation: The clean-up applied to the text of each section.
            subparts: The subpart numbers to keep, such as ``571``.
        """
        self._normalisation = normalisation
        self._subparts = tuple(subparts)

    def parse(self, document: DocumentSpec, path: Path) -> ParsedDocument:
        """
        Parse the regulation XML.

        Args:
            document: The manifest entry of the regulations.
            path: The downloaded XML. It is read, never changed.

        Returns:
            The canonical text, with one passage per kept section, in
            document order.

        Raises:
            ParseError: If the file isn't valid XML, has no ``Body``, or has
                no section for one of the subparts.
        """
        body = _read_body(document, path)
        parts = section_parts(body, self._subparts)
        labels = [
            part.location.label or ""
            for part in parts
            if isinstance(part.location, SectionLocation)
        ]
        missing = [
            subpart
            for subpart in self._subparts
            if not any(label.startswith(f"{subpart}.") for label in labels)
        ]

        if missing:
            names = ", ".join(missing)

            raise ParseError(f"{document.id}: no section of Subpart {names} in {path}")

        text, passages = assemble(document.id, parts, self._normalisation)

        return ParsedDocument(
            document_id=document.id,
            source_sha256=file_sha256(path),
            parser=ParserInfo(name=PARSER_NAME, version=library_version()),
            text=text,
            passages=passages,
        )


def section_parts(body: etree._Element, subparts: Sequence[str]) -> list[TextPart]:
    """
    Cut the body of the regulations into one part per kept section.

    A part's text starts with the headings that came after the previous
    section, of any subpart, so the canonical text keeps them in order.

    Args:
        body: The ``Body`` element.
        subparts: The subpart numbers to keep.

    Returns:
        The kept sections, in document order.
    """
    prefixes = tuple(f"{subpart}." for subpart in subparts)
    headings: dict[int, str] = {}
    new_headings: list[str] = []
    parts = []

    for element in body:
        if element.tag == "Heading":
            level = int(element.get("level", "1"))
            title = heading_text(element)
            headings = {lvl: t for lvl, t in headings.items() if lvl < level}
            headings[level] = title

            if title:
                new_headings.append(title)

        elif element.tag == "Section":
            label = _inline_text(element.find("Label"))

            if label.startswith(prefixes):
                path = tuple(t for _, t in sorted(headings.items()) if t)
                location = SectionLocation(label=label, heading_path=path)
                lines = new_headings + block_lines(element)
                parts.append(TextPart(location, "\n".join(lines)))

            new_headings = []

    return parts


def heading_text(heading: etree._Element) -> str:
    """
    Read a heading's title, such as ``PART V Airworthiness``.

    Args:
        heading: A ``Heading`` element.

    Returns:
        Its label and title text. A ``HistoricalNote`` stays out of it.
    """
    pieces = [
        _inline_text(child)
        for child in heading
        if isinstance(child.tag, str) and child.tag != "HistoricalNote"
    ]

    return " ".join(piece for piece in pieces if piece)


def block_lines(element: etree._Element, labels: Sequence[str] = ()) -> list[str]:
    """
    Turn a section, or a block inside it, into lines of text.

    Each ``Text`` becomes one line, led by the labels above it that no line
    has used yet, such as ``571.02 (1)`` for the first subsection of 571.02.
    Cross-references and other inline elements stay inside their line. A
    ``HistoricalNote`` becomes one line, its items separated by semicolons,
    as the consolidated regulations print it.

    Args:
        element: A ``Section``, ``Subsection``, ``Paragraph`` or deeper block.
        labels: The labels of the enclosing blocks not used yet.

    Returns:
        The lines, in document order.
    """
    lines: list[str] = []
    pending = list(labels)

    for child in element:
        if not isinstance(child.tag, str):
            continue

        if child.tag == "Label":
            pending.append(_inline_text(child))
        elif child.tag == "Text":
            lines.append(" ".join([*pending, _inline_text(child)]))
            pending = []
        elif child.tag == "HistoricalNote":
            lines.append("; ".join(_inline_text(item) for item in child))
        else:
            lines.extend(block_lines(child, pending))
            pending = []

    if pending:
        lines.append(" ".join(pending))

    return lines


def library_version() -> str:
    """
    Name the versions of lxml and of the libxml2 it uses.

    Returns:
        A version such as ``6.1.3 (libxml2 2.14.6)``.
    """
    libxml2 = ".".join(str(number) for number in etree.LIBXML_VERSION)

    return f"{etree.__version__} (libxml2 {libxml2})"


def _read_body(document: DocumentSpec, path: Path) -> etree._Element:
    # Entities are never resolved and nothing is fetched from the network,
    # so a downloaded file can't make the parser read other files.
    parser = etree.XMLParser(resolve_entities=False, no_network=True)

    try:
        tree = etree.parse(str(path), parser)
    except (OSError, etree.XMLSyntaxError) as error:
        raise ParseError(f"{document.id}: can't read {path} as XML: {error}") from error

    body = tree.getroot().find("Body")

    if body is None:
        raise ParseError(f"{document.id}: {path} has no Body element")

    return body


def _inline_text(element: etree._Element | None) -> str:
    # The XML's own line breaks and indentation carry no meaning.
    if element is None:
        return ""

    return " ".join("".join(element.itertext()).split())
