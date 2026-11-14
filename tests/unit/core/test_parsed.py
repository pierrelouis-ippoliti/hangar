from typing import Any

import pydantic
import pytest

from hangar.core.parsed import (
    PageLocation,
    ParsedDocument,
    Passage,
    SectionLocation,
    passage_id,
)

DOCUMENT_ID = "example-handbook"
FAKE_SHA256 = "0123456789abcdef" * 4

# Three pages: "first page\n\n" (0-12), "second page\n\n" (12-25), "third" (25-30).
TEXT = "first page\n\nsecond page\n\nthird"


def page(index: int, start: int, end: int, label: str | None = None) -> Passage:
    location = PageLocation(page_index=index, page_label=label)

    return Passage(
        id=passage_id(DOCUMENT_ID, location), location=location, start=start, end=end
    )


def document(passages: list[Passage] | None = None, **changes: Any) -> ParsedDocument:
    fields: dict[str, Any] = {
        "document_id": DOCUMENT_ID,
        "source_sha256": FAKE_SHA256,
        "parser": {"name": "example-parser", "version": "1.0"},
        "text": TEXT,
        "passages": passages
        if passages is not None
        else [page(1, 0, 12), page(2, 12, 25), page(3, 25, 30)],
        "warnings": [],
    }
    fields.update(changes)

    return ParsedDocument.model_validate(fields)


def test_page_passage_id_uses_the_one_based_page_index() -> None:
    location = PageLocation(page_index=142, page_label="7-12")

    assert passage_id("faa-h-8083-31b", location) == "faa-h-8083-31b#p142"


def test_section_passage_id_uses_the_section_label() -> None:
    location = SectionLocation(label="571.10", heading_path=("Part V", "Subpart 71"))

    assert passage_id("car-sor-96-433", location) == "car-sor-96-433#s571.10"


def test_front_matter_passage_id_is_front() -> None:
    location = SectionLocation(label=None, heading_path=("Standard 571",))

    assert passage_id("tc-std-571", location) == "tc-std-571#front"


def test_section_labels_with_spaces_or_hashes_are_rejected() -> None:
    for label in ["571 10", "a#b", ""]:
        with pytest.raises(pydantic.ValidationError):
            SectionLocation(label=label, heading_path=())


def test_page_index_starts_at_one() -> None:
    with pytest.raises(pydantic.ValidationError):
        PageLocation(page_index=0, page_label=None)


def test_passage_kind_comes_from_its_location() -> None:
    section = SectionLocation(label="1.1", heading_path=())
    passage = Passage(id=passage_id("ac", section), location=section, start=0, end=3)

    assert page(1, 0, 12).kind == "page"
    assert passage.kind == "section"


def test_passage_end_cannot_come_before_its_start() -> None:
    with pytest.raises(pydantic.ValidationError, match="end"):
        page(1, 5, 4)


def test_valid_document_is_accepted() -> None:
    parsed = document()

    assert parsed.text == TEXT
    assert [p.id for p in parsed.passages] == [
        "example-handbook#p1",
        "example-handbook#p2",
        "example-handbook#p3",
    ]


def test_passages_with_a_gap_are_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="gap"):
        document([page(1, 0, 12), page(2, 13, 25), page(3, 25, 30)])


def test_overlapping_passages_are_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="overlap"):
        document([page(1, 0, 12), page(2, 11, 25), page(3, 25, 30)])


def test_passages_must_start_at_the_beginning_of_the_text() -> None:
    with pytest.raises(pydantic.ValidationError, match="offset 0"):
        document([page(1, 1, 12), page(2, 12, 25), page(3, 25, 30)])


def test_passages_must_reach_the_end_of_the_text() -> None:
    with pytest.raises(pydantic.ValidationError, match="end of the text"):
        document([page(1, 0, 12), page(2, 12, 25), page(3, 25, 29)])


def test_a_document_needs_at_least_one_passage() -> None:
    with pytest.raises(pydantic.ValidationError):
        document([], text="")


def test_duplicate_passage_ids_are_rejected() -> None:
    with pytest.raises(pydantic.ValidationError, match="duplicate"):
        document([page(1, 0, 12), page(1, 12, 25), page(3, 25, 30)])


def test_passage_id_must_match_its_document_and_location() -> None:
    location = PageLocation(page_index=2, page_label=None)
    wrong = Passage(id="example-handbook#p9", location=location, start=12, end=25)

    with pytest.raises(pydantic.ValidationError, match="example-handbook#p2"):
        document([page(1, 0, 12), wrong, page(3, 25, 30)])


def test_range_spanning_two_pages_maps_to_both() -> None:
    covered = document().passages_in_range(5, 20)

    assert [p.id for p in covered] == ["example-handbook#p1", "example-handbook#p2"]


def test_range_inside_one_page_maps_to_that_page() -> None:
    covered = document().passages_in_range(13, 20)

    assert [p.id for p in covered] == ["example-handbook#p2"]


def test_range_ending_on_a_boundary_stops_before_the_next_page() -> None:
    covered = document().passages_in_range(0, 12)

    assert [p.id for p in covered] == ["example-handbook#p1"]


def test_whole_text_maps_to_every_page() -> None:
    covered = document().passages_in_range(0, len(TEXT))

    assert len(covered) == 3


def test_empty_passages_are_never_covered() -> None:
    # Page 2 is empty: a zero-length passage at offset 12.
    parsed = document(
        [page(1, 0, 12), page(2, 12, 12), page(3, 12, 30)],
        text="first page\n\nsecond page\n\nthird",
    )

    covered = parsed.passages_in_range(5, 20)

    assert [p.id for p in covered] == ["example-handbook#p1", "example-handbook#p3"]


def test_range_outside_the_text_is_refused() -> None:
    parsed = document()

    for start, end in [(-1, 5), (5, 5), (8, 4), (0, len(TEXT) + 1)]:
        with pytest.raises(ValueError, match="range"):
            parsed.passages_in_range(start, end)


def test_document_survives_a_json_round_trip() -> None:
    section = SectionLocation(label="571.10", heading_path=("Part V", "Subpart 71"))
    parsed = document(
        [
            page(1, 0, 12, label="i"),
            Passage(
                id=passage_id(DOCUMENT_ID, section), location=section, start=12, end=30
            ),
        ],
        warnings=[
            {
                "code": "empty_page",
                "passage_id": "example-handbook#p1",
                "message": "no text",
            }
        ],
    )

    assert ParsedDocument.model_validate_json(parsed.model_dump_json()) == parsed


def test_warning_codes_are_snake_case() -> None:
    with pytest.raises(pydantic.ValidationError):
        document(warnings=[{"code": "Empty Page", "passage_id": None, "message": "x"}])


def test_parsed_documents_cannot_be_changed() -> None:
    parsed = document()

    with pytest.raises(pydantic.ValidationError):
        parsed.text = "changed"  # type: ignore[misc]
