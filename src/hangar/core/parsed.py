"""
Parsed documents: one canonical text per document, split into passages.

A parser turns a downloaded file into a canonical text and a list of
passages: one per PDF page, or one per numbered section of a regulation,
standard or advisory circular. Passages are character ranges of the text,
and together they cover it exactly once, with no gap and no overlap. Later
stages work with offsets into this text, so the pages or sections a chunk
covers are computed from its offsets, never guessed.

Offsets belong to one parse: a new parser gives new offsets. Passage IDs
derive from the document and the location, such as ``faa-h-8083-31b#p142``
or ``car-sor-96-433#s571.10``, so they stay the same from one run to the
next.
"""

from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    model_validator,
)

from hangar.core.corpus import DOCUMENT_ID_PATTERN, SHA256_PATTERN


class ParsedModel(BaseModel):
    """
    A part of a parsed document: frozen, and with no unknown fields.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class PageLocation(ParsedModel):
    """
    Where a page passage sits in a PDF.

    Attributes:
        kind: Always ``page``; tells page and section locations apart in JSON.
        page_index: The 1-based position of the page in the file. It is
            canonical: unambiguous, and it links straight to the page.
        page_label: The page number printed on the page, such as ``7-12``,
            when the PDF provides one; technicians cite this one.
    """

    kind: Literal["page"] = "page"
    page_index: PositiveInt
    page_label: str | None


class SectionLocation(ParsedModel):
    """
    Where a section passage sits in a regulation, standard or circular.

    Attributes:
        kind: Always ``section``; tells page and section locations apart
            in JSON.
        label: The section number, such as ``571.10`` or ``4.1.1``, or None
            for the front matter: the text before the first numbered
            section, such as a title and a table of contents.
        heading_path: The headings above the section, from the outermost
            to its own, such as ``("Part V — Airworthiness", "Subpart 71 —
            Aircraft Maintenance Requirements", "Maintenance Release")``.
    """

    kind: Literal["section"] = "section"
    label: str | None = Field(pattern=r"^[0-9A-Za-z][0-9A-Za-z.\-]*$")
    heading_path: tuple[str, ...]


Location = Annotated[PageLocation | SectionLocation, Field(discriminator="kind")]


def passage_id(document_id: str, location: PageLocation | SectionLocation) -> str:
    """
    Derive a passage's ID from its document and location.

    Args:
        document_id: The manifest ID of the document, such as
            ``faa-h-8083-31b``.
        location: The page or section the passage covers.

    Returns:
        ``<document>#p<page index>`` for a page, ``<document>#s<label>`` for
        a section, and ``<document>#front`` for the front matter.
    """
    if isinstance(location, PageLocation):
        return f"{document_id}#p{location.page_index}"

    if location.label is None:
        return f"{document_id}#front"

    return f"{document_id}#s{location.label}"


class Passage(ParsedModel):
    """
    One page or section of a document, as a range of its canonical text.

    Attributes:
        id: The ID from ``passage_id``, such as ``faa-h-8083-31b#p142``.
        location: The page or section the passage covers.
        start: The offset of the passage's first character.
        end: The offset just after its last character. An empty page has
            ``start == end``.
    """

    id: str = Field(min_length=1)
    location: Location
    start: NonNegativeInt
    end: NonNegativeInt

    @property
    def kind(self) -> Literal["page", "section"]:
        """
        Whether the passage is a page or a section.
        """
        return self.location.kind

    @model_validator(mode="after")
    def _check_end_is_not_before_start(self) -> Self:
        if self.end < self.start:
            raise ValueError(
                f"passage {self.id}: end ({self.end}) comes before start ({self.start})"
            )

        return self


class ParseWarning(ParsedModel):
    """
    Something a parser noticed but did not stop for, such as an empty page.

    Attributes:
        code: A short snake_case name for the kind of problem, such as
            ``empty_page``; the parse report counts warnings by code.
        passage_id: The passage the warning is about, or None when it is
            about the whole document.
        message: What was found, in plain words.
    """

    code: str = Field(pattern=r"^[a-z]+(_[a-z]+)*$")
    passage_id: str | None
    message: str = Field(min_length=1)


class ParserInfo(ParsedModel):
    """
    Which parser produced a document.

    Attributes:
        name: The parser's name, such as ``pypdfium2``.
        version: The version of the library behind it, so a library upgrade
            shows in the output.
    """

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)


class ParsedDocument(ParsedModel):
    """
    A document's canonical text and the passages that cover it.

    Attributes:
        document_id: The manifest ID of the document.
        source_sha256: The SHA-256 of the downloaded file that was parsed.
        parser: The parser that produced the document.
        text: The canonical text, after normalisation.
        passages: The pages or sections, in text order. They cover the text
            exactly once: the first starts at 0, each one ends where the
            next starts, and the last ends at the end of the text.
        warnings: What the parser noticed, such as empty pages.
    """

    document_id: str = Field(pattern=DOCUMENT_ID_PATTERN)
    source_sha256: str = Field(pattern=SHA256_PATTERN)
    parser: ParserInfo
    text: str
    passages: tuple[Passage, ...] = Field(min_length=1)
    warnings: tuple[ParseWarning, ...] = ()

    @model_validator(mode="after")
    def _check_passages(self) -> Self:
        self._check_ids()
        self._check_coverage()

        return self

    def _check_ids(self) -> None:
        seen = set()

        for passage in self.passages:
            expected = passage_id(self.document_id, passage.location)

            if passage.id != expected:
                raise ValueError(
                    f"passage {passage.id} should have the ID {expected}, "
                    "from its document and location"
                )

            if passage.id in seen:
                raise ValueError(f"duplicate passage ID {passage.id}")

            seen.add(passage.id)

    def _check_coverage(self) -> None:
        first, last = self.passages[0], self.passages[-1]

        if first.start != 0:
            raise ValueError(
                f"passage {first.id} starts at {first.start}; "
                "the first passage must start at offset 0"
            )

        for before, after in zip(self.passages, self.passages[1:], strict=False):
            if after.start > before.end:
                raise ValueError(
                    f"gap between passage {before.id}, which ends at {before.end}, "
                    f"and passage {after.id}, which starts at {after.start}"
                )

            if after.start < before.end:
                raise ValueError(
                    f"passage {after.id}, which starts at {after.start}, "
                    f"overlaps passage {before.id}, which ends at {before.end}"
                )

        if last.end != len(self.text):
            raise ValueError(
                f"passage {last.id} ends at {last.end}, but the end of the text "
                f"is at {len(self.text)}"
            )

    def passages_in_range(self, start: int, end: int) -> tuple[Passage, ...]:
        """
        List the passages that a range of the text covers, even in part.

        This is how a chunk's pages or sections are found from its offsets.
        Empty passages, such as blank pages, hold no text, so no range
        covers them.

        Args:
            start: The offset of the range's first character.
            end: The offset just after its last character.

        Returns:
            The passages that share at least one character with the range,
            in text order.

        Raises:
            ValueError: If the range is empty or reaches outside the text.
        """
        if not 0 <= start < end <= len(self.text):
            raise ValueError(
                f"range {start}-{end} is empty or outside the text, "
                f"which has {len(self.text)} characters"
            )

        return tuple(
            p
            for p in self.passages
            if p.start < p.end and p.start < end and p.end > start
        )


class ParsedFile(ParsedModel):
    """
    A parsed document as the parse stage writes it.

    The parser can't know the configuration of the run, so the parse stage
    adds its hash next to the document.

    Attributes:
        config_hash: The hash of the pipeline configuration of the run.
        document: The parsed document.
    """

    config_hash: str = Field(pattern=SHA256_PATTERN)
    document: ParsedDocument
