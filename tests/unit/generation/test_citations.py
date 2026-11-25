from hangar.core.chunks import PassageRef, chunk_id
from hangar.core.citations import Citation
from hangar.core.prompts import Source
from hangar.generation.citations import parse_citations
from tests.builders import page, section

HANDBOOK = "faa-h-8083-30b"
REGULATION = "car-sor-96-433"


def source(number: int, document_id: str, passages: tuple[PassageRef, ...]) -> Source:
    return Source(
        number=number,
        chunk_id=chunk_id(document_id, "fixed512", number * 100, number * 100 + 50),
        document_id=document_id,
        passages=passages,
    )


SOURCES = (
    source(
        1,
        HANDBOOK,
        (
            page(323, "7-79", document_id=HANDBOOK),
            page(324, "7-80", document_id=HANDBOOK),
        ),
    ),
    source(2, REGULATION, (section("571.10", document_id=REGULATION),)),
)


def test_a_marker_in_range_gives_a_valid_citation_with_its_source() -> None:
    citations = parse_citations("Torque the bolt to the stated value [2].", SOURCES)

    assert citations == (
        Citation(
            marker=2,
            valid=True,
            chunk_id=SOURCES[1].chunk_id,
            document_id=REGULATION,
            passages=(section("571.10", document_id=REGULATION),),
        ),
    )


def test_citations_follow_the_order_of_first_appearance() -> None:
    citations = parse_citations("Inspect it [2]. Then sign the record [1][2].", SOURCES)

    assert [citation.marker for citation in citations] == [2, 1]


def test_a_repeated_marker_gives_one_citation() -> None:
    citations = parse_citations("First claim [1]. Second claim [1].", SOURCES)

    assert len(citations) == 1


def test_a_marker_past_the_last_source_is_invalid() -> None:
    citations = parse_citations("A claim [3].", SOURCES)

    assert citations == (
        Citation(marker=3, valid=False, chunk_id=None, document_id=None, passages=()),
    )


def test_marker_zero_is_invalid_because_sources_start_at_one() -> None:
    (citation,) = parse_citations("A claim [0].", SOURCES)

    assert not citation.valid


def test_every_marker_is_invalid_when_there_are_no_sources() -> None:
    (citation,) = parse_citations("A claim [1].", ())

    assert not citation.valid


def test_valid_and_invalid_markers_are_reported_together() -> None:
    citations = parse_citations("One [1]. Two [7]. Three [2].", SOURCES)

    assert [(citation.marker, citation.valid) for citation in citations] == [
        (1, True),
        (7, False),
        (2, True),
    ]


def test_an_answer_with_no_marker_gives_no_citation() -> None:
    assert parse_citations("The sources do not cover this question.", SOURCES) == ()


def test_brackets_that_hold_no_number_are_not_markers() -> None:
    answer = "Set the switch to [OFF], see [a] and [1, 2] or [ 1 ]."

    assert parse_citations(answer, SOURCES) == ()
