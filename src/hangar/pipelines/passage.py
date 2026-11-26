"""
Showing the parsed text of one page or section, to copy evidence quotes.

The seed questions quote the parsed text word for word, so the quotes are
copied from what ``hangar passage`` prints rather than from the PDF or the
web page, whose characters can differ after normalisation.
"""

from hangar.core.config import PipelineConfig
from hangar.core.errors import HangarError
from hangar.core.parsed import PageLocation, ParsedDocument, ParsedFile, Passage
from hangar.pipelines.settings import Settings


class PassageError(HangarError):
    """A parsed document or a passage that can't be found."""


def load_parsed_document(
    settings: Settings, config: PipelineConfig, document_id: str
) -> ParsedDocument:
    """
    Read one parsed document of the configured snapshot.

    Args:
        settings: Where Hangar runs. The document is read from
            ``<data folder>/parsed/<snapshot>/<document ID>.json``.
        config: The pipeline configuration, which names the snapshot.
        document_id: The manifest ID of the document, such as
            ``faa-h-8083-31b``.

    Returns:
        The parsed document.

    Raises:
        PassageError: If the document has no parsed file.
    """
    path = settings.data_dir / "parsed" / config.corpus.snapshot / f"{document_id}.json"

    if not path.is_file():
        raise PassageError(
            f"{path} is missing; check the document ID, or run hangar parse first"
        )

    return ParsedFile.model_validate_json(path.read_text(encoding="utf-8")).document


def format_passage(document: ParsedDocument, location: str) -> str:
    """
    Write one passage for the screen: where it is, then its parsed text.

    Args:
        document: The parsed document.
        location: The passage's location as an evidence item writes it:
            ``p142``, ``s571.10`` or ``front``.

    Returns:
        A header and the passage's text, such as::

            passage:  faa-h-8083-30b#p142
            evidence: "document_id": "faa-h-8083-30b", "location": "p142"
            page:     index 142, printed label 7-12

            <the parsed text of the page>

        The ``evidence`` line can be pasted into an evidence item.

    Raises:
        PassageError: If the document has no passage at this location.
    """
    passage = document.passage(f"{document.document_id}#{location}")

    if passage is None:
        raise PassageError(
            f"{document.document_id} has no passage at {location}. A location "
            "looks like p142 (a PDF page index), s571.10 (a section) or front; "
            f"run hangar passage {document.document_id} to list them"
        )

    header = [
        f"passage:  {passage.id}",
        f'evidence: "document_id": "{document.document_id}", "location": "{location}"',
        _describe_location(passage),
    ]

    return "\n".join([*header, "", document.passage_text(passage)])


def format_locations(document: ParsedDocument) -> str:
    """
    List a document's passages, one line each, to find a location.

    Args:
        document: The parsed document.

    Returns:
        One line per passage in text order: its location as an evidence
        item writes it, then its printed page label or its own heading,
        such as ``p142  printed label 7-12`` or
        ``s571.03  571.03 Recording of Maintenance and Elementary Work``.
        An empty page is marked as such.
    """
    locations = [_location(document, passage) for passage in document.passages]
    width = max(len(location) for location in locations) + 2

    return "\n".join(
        f"{location:<{width}}{_summary(passage)}"
        for location, passage in zip(locations, document.passages, strict=True)
    )


def _location(document: ParsedDocument, passage: Passage) -> str:
    return passage.id.removeprefix(f"{document.document_id}#")


def _describe_location(passage: Passage) -> str:
    location = passage.location

    if isinstance(location, PageLocation):
        return f"page:     index {location.page_index}, {_printed_label(location)}"

    return f"section:  {' > '.join(location.heading_path)}"


def _summary(passage: Passage) -> str:
    location = passage.location

    if isinstance(location, PageLocation):
        summary = _printed_label(location)
    else:
        summary = location.heading_path[-1] if location.heading_path else ""

    if passage.start == passage.end:
        summary += ", empty"

    return summary


def _printed_label(location: PageLocation) -> str:
    label = location.page_label

    return f"printed label {label}" if label else "no printed label"
