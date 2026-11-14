"""
The parse report and the data checks that every parsed document must pass.

The report is committed (``results/<run name>/parse-report.json``), so it
records only values that change with the results: the configuration hash,
the hash of each file read, the parser and library versions, and counts.
It holds no time, run ID or commit, so parsing the same files with the same
configuration and code gives the same report.
"""

from collections.abc import Sequence

from pydantic import Field, NonNegativeInt, PositiveInt

from hangar.core.config import ParseChecksConfig
from hangar.core.corpus import SHA256_PATTERN, DocumentFormat, DocumentSpec
from hangar.core.errors import HangarError
from hangar.core.parsed import (
    PageLocation,
    ParsedDocument,
    ParsedModel,
    ParserInfo,
    ParseWarning,
    SectionLocation,
)


class DocumentReport(ParsedModel):
    """
    What parsing one document gave.

    Attributes:
        document_id: The manifest ID of the document.
        format: The format of the file read.
        source_sha256: The SHA-256 of the file read.
        parser: The parser and the version of its library.
        characters: The length of the canonical text.
        passages: The number of passages.
        pages: The number of PDF pages, or None for other formats.
        empty_pages: The number of PDF pages with no text, or None.
        garbled_pages: The number of PDF pages with unreadable characters,
            or None.
        sections: The number of numbered sections, front matter left out,
            or None for PDFs.
        warnings: The parser's warnings.
    """

    document_id: str
    format: DocumentFormat
    source_sha256: str = Field(pattern=SHA256_PATTERN)
    parser: ParserInfo
    characters: NonNegativeInt
    passages: PositiveInt
    pages: NonNegativeInt | None
    empty_pages: NonNegativeInt | None
    garbled_pages: NonNegativeInt | None
    sections: NonNegativeInt | None
    warnings: tuple[ParseWarning, ...]


class ParseReport(ParsedModel):
    """
    What parsing a corpus snapshot gave, one entry per document.

    Attributes:
        snapshot: The corpus snapshot, such as ``c1``.
        config_hash: The hash of the pipeline configuration of the run.
        documents: One report per document, in manifest order.
    """

    snapshot: str
    config_hash: str = Field(pattern=SHA256_PATTERN)
    documents: tuple[DocumentReport, ...]


class ParseCheckError(HangarError):
    """
    Parsed documents outside the thresholds of the configuration.

    The message has one line per problem, each starting with the document
    ID.

    Attributes:
        problems: Every problem found, in manifest order.
    """

    def __init__(self, problems: Sequence[str]) -> None:
        """
        Create the error.

        Args:
            problems: Every problem found. At least one.
        """
        self.problems = tuple(problems)
        lines = [f"{len(self.problems)} parse checks failed:", *self.problems]
        super().__init__("\n".join(lines))


def document_report(document: DocumentSpec, parsed: ParsedDocument) -> DocumentReport:
    """
    Count what parsing one document gave.

    Args:
        document: The manifest entry of the document.
        parsed: The parsed document.

    Returns:
        Its report. Page counts are set for PDFs, section counts for the
        other formats.
    """
    pages = [p for p in parsed.passages if isinstance(p.location, PageLocation)]
    labels = [
        p.location.label
        for p in parsed.passages
        if isinstance(p.location, SectionLocation)
    ]
    garbled = [w for w in parsed.warnings if w.code == "garbled_page"]

    return DocumentReport(
        document_id=document.id,
        format=document.format,
        source_sha256=parsed.source_sha256,
        parser=parsed.parser,
        characters=len(parsed.text),
        passages=len(parsed.passages),
        pages=len(pages) if pages else None,
        empty_pages=sum(1 for p in pages if p.start == p.end) if pages else None,
        garbled_pages=len(garbled) if pages else None,
        sections=sum(1 for label in labels if label) if labels else None,
        warnings=parsed.warnings,
    )


def check_report(report: ParseReport, checks: ParseChecksConfig) -> list[str]:
    """
    Find the documents outside the thresholds of the configuration.

    Args:
        report: The parse report.
        checks: The thresholds.

    Returns:
        One message per problem, each starting with the document ID, in
        manifest order. Empty when every document passes.
    """
    problems = []

    for document in report.documents:
        problems.extend(_document_problems(document, checks))

    return problems


def _document_problems(
    document: DocumentReport, checks: ParseChecksConfig
) -> list[str]:
    name = document.document_id
    problems = []

    if document.characters < checks.min_characters:
        problems.append(
            f"{name}: {document.characters} characters, "
            f"fewer than the minimum of {checks.min_characters}"
        )

    if document.sections is not None and document.sections < checks.min_sections:
        problems.append(
            f"{name}: {document.sections} numbered sections, "
            f"fewer than the minimum of {checks.min_sections}"
        )

    if document.pages:
        for kind, count, limit in [
            ("empty", document.empty_pages or 0, checks.max_empty_page_share),
            ("garbled", document.garbled_pages or 0, checks.max_garbled_page_share),
        ]:
            share = count / document.pages

            if share > limit:
                problems.append(
                    f"{name}: {count} of {document.pages} pages are {kind} "
                    f"({share:.1%}), more than the maximum of {limit:.1%}"
                )

    return problems
