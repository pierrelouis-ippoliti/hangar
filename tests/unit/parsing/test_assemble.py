from hangar.core.config import NormalisationConfig
from hangar.core.parsed import (
    PageLocation,
    ParsedDocument,
    ParserInfo,
    SectionLocation,
)
from hangar.parsing.assemble import TextPart, assemble

NORMALISATION = NormalisationConfig(unicode_form="NFKC", collapse_whitespace=True)


def pages(*texts: str) -> list[TextPart]:
    return [
        TextPart(PageLocation(page_index=i, page_label=None), text)
        for i, text in enumerate(texts, start=1)
    ]


def spans(text: str, parts: list[TextPart]) -> list[str]:
    _, passages = assemble("example", parts, NORMALISATION)

    return [text[p.start : p.end] for p in passages]


def test_each_passage_owns_the_separator_after_it() -> None:
    parts = pages("first page", "second page", "third")
    text, passages = assemble("example", parts, NORMALISATION)

    assert text == "first page\n\nsecond page\n\nthird"
    assert spans(text, parts) == ["first page\n\n", "second page\n\n", "third"]
    assert [p.id for p in passages] == ["example#p1", "example#p2", "example#p3"]


def test_parts_are_normalised_and_trimmed() -> None:
    text, _ = assemble("example", pages("  ﬁrst\r\n page  ", "\tsecond"), NORMALISATION)

    assert text == "first\n page\n\nsecond"


def test_an_empty_part_keeps_a_zero_length_passage() -> None:
    parts = pages("first", "  \r\n ", "third")
    text, passages = assemble("example", parts, NORMALISATION)

    assert text == "first\n\nthird"
    assert spans(text, parts) == ["first\n\n", "", "third"]
    assert passages[1].start == passages[1].end == 7


def test_empty_parts_at_the_end_leave_no_trailing_separator() -> None:
    text, passages = assemble("example", pages("first", "", " "), NORMALISATION)

    assert text == "first"
    assert [(p.start, p.end) for p in passages] == [(0, 5), (5, 5), (5, 5)]


def test_section_parts_get_section_ids() -> None:
    parts = [
        TextPart(SectionLocation(label=None, heading_path=("Title",)), "Title"),
        TextPart(SectionLocation(label="1.1", heading_path=("1.0", "1.1")), "1.1"),
    ]
    _, passages = assemble("tc-ac-571-002", parts, NORMALISATION)

    assert [p.id for p in passages] == ["tc-ac-571-002#front", "tc-ac-571-002#s1.1"]


def test_assembled_passages_make_a_valid_document() -> None:
    text, passages = assemble("example", pages("a", "", "b c", ""), NORMALISATION)

    parsed = ParsedDocument(
        document_id="example",
        source_sha256="0" * 64,
        parser=ParserInfo(name="test", version="1"),
        text=text,
        passages=passages,
        warnings=(),
    )

    assert parsed.passages_in_range(0, len(text)) == (passages[0], passages[2])
