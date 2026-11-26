import datetime

from hangar.core.citations import Citation
from hangar.core.completions import Completion
from hangar.core.records import AnswerRecord, ScoredChunkRef
from hangar.generation.presentation import (
    STUDY_AID_NOTICE,
    attribution,
    format_answer,
    source_label,
)
from tests.builders import (
    answer_record,
    chunk,
    citation,
    completion,
    document_spec,
    page,
    scored,
    section,
)

HANDBOOK = document_spec(
    id="faa-h-8083-31b",
    title="FAA-H-8083-31B, Aviation Maintenance Technician Handbook – Airframe",
    official_url="https://www.faa.gov/airframe.pdf",
)
REGULATIONS = document_spec(
    id="car-sor-96-433",
    title="Canadian Aviation Regulations (SOR/96-433)",
    authority="TC",
    type="regulation",
    format="xml",
    official_url="https://laws-lois.justice.gc.ca/eng/regulations/SOR-96-433/",
    content_date=datetime.date(2026, 6, 18),
)
STANDARD = document_spec(
    id="tc-std-571",
    title="Standard 571 – Maintenance",
    authority="TC",
    type="standard",
    format="html",
    official_url="https://tc.canada.ca/standard-571",
    content_date=datetime.date(2010, 12, 30),
)
CIRCULAR = document_spec(
    id="tc-ac-571-025",
    title="AC 571-025, Maintenance of Emergency Locator Transmitters (ELTs)",
    authority="TC",
    type="advisory_circular",
    format="html",
    official_url="https://tc.canada.ca/ac-571-025",
)
DOCUMENTS = {d.id: d for d in (HANDBOOK, REGULATIONS, STANDARD, CIRCULAR)}

AIRFRAME_CHUNK = chunk(
    "Replace the battery.",
    passages=[
        page(142, "7-12", document_id=HANDBOOK.id),
        page(143, "7-13", document_id=HANDBOOK.id),
    ],
)
STANDARD_CHUNK = chunk(
    "Record the work.", passages=[section("571.10", document_id=STANDARD.id)]
)


def answer(text: str, citations: tuple[Citation, ...]) -> AnswerRecord:
    retrieved = (AIRFRAME_CHUNK, STANDARD_CHUNK)

    return answer_record(
        scored_chunks=tuple(
            ScoredChunkRef.of(scored(c, rank=rank))
            for rank, c in enumerate(retrieved, start=1)
        ),
        completion=Completion.model_validate(
            completion().model_dump() | {"text": text}
        ),
        citations=citations,
    )


def invalid(marker: int) -> Citation:
    return Citation(
        marker=marker, valid=False, chunk_id=None, document_id=None, passages=()
    )


def shown(record: AnswerRecord) -> str:
    return format_answer(record, DOCUMENTS, "c1")


def test_each_label_joins_the_authority_and_the_kind_of_document() -> None:
    assert source_label(HANDBOOK) == "FAA handbook guidance"
    assert source_label(REGULATIONS) == "Transport Canada regulation"
    assert source_label(STANDARD) == "Transport Canada standard"
    assert source_label(CIRCULAR) == "Transport Canada advisory circular"


def test_an_faa_handbook_is_attributed_to_the_faa_with_its_official_url() -> None:
    assert attribution(HANDBOOK) == (
        "FAA-H-8083-31B, Aviation Maintenance Technician Handbook – Airframe, "
        "Federal Aviation Administration. "
        "The official version is at https://www.faa.gov/airframe.pdf."
    )


def test_the_regulations_say_they_are_not_the_official_version() -> None:
    assert attribution(REGULATIONS) == (
        "Canadian Aviation Regulations (SOR/96-433), Department of Justice Canada. "
        "Not the official version; the official version is at "
        "https://laws-lois.justice.gc.ca/eng/regulations/SOR-96-433/."
    )


def test_transport_canada_pages_are_copies_and_hangar_is_not_endorsed() -> None:
    assert attribution(CIRCULAR) == (
        "AC 571-025, Maintenance of Emergency Locator Transmitters (ELTs), "
        "Transport Canada. A copy of the version available at "
        "https://tc.canada.ca/ac-571-025. "
        "Hangar is not affiliated with or endorsed by Transport Canada."
    )


def test_the_answer_comes_first_then_each_cited_source() -> None:
    record = answer(
        "Replace the battery [1]. Record it [2].",
        (citation(AIRFRAME_CHUNK, 1), citation(STANDARD_CHUNK, 2)),
    )

    assert shown(record).startswith(
        "Replace the battery [1]. Record it [2].\n"
        "\n"
        "Sources:\n"
        "[1] faa-h-8083-31b, p. 142 (7-12) to p. 143 (7-13)\n"
        "    FAA handbook guidance, content date 2023-07-21\n"
        f"    {attribution(HANDBOOK)}\n"
        "[2] tc-std-571, § 571.10\n"
        "    Transport Canada standard, content date 2010-12-30\n"
        f"    {attribution(STANDARD)}\n"
    )


def test_an_invalid_marker_is_flagged() -> None:
    record = answer(
        "Replace the battery [1][7].", (citation(AIRFRAME_CHUNK, 1), invalid(7))
    )

    assert "[7] invalid marker: no source has this number\n" in shown(record)


def test_an_answer_without_a_valid_citation_says_it_cites_no_source() -> None:
    text = shown(answer("Replace the battery [9].", (invalid(9),)))

    assert "[9] invalid marker" in text
    assert "The answer cites no source" in text


def test_an_answer_with_a_valid_citation_does_not_say_it_cites_none() -> None:
    record = answer("Replace the battery [1].", (citation(AIRFRAME_CHUNK, 1),))

    assert "cites no source" not in shown(record)


def test_the_snapshot_is_named_and_the_study_aid_notice_comes_last() -> None:
    for record in (
        answer("Replace the battery [1].", (citation(AIRFRAME_CHUNK, 1),)),
        answer("The sources don't say.", ()),
    ):
        text = shown(record)

        assert "\nAnswered from corpus snapshot c1.\n" in text
        assert text.endswith(f"\n\n{STUDY_AID_NOTICE}")


def test_the_notice_says_hangar_is_not_approved_maintenance_data() -> None:
    assert "not approved maintenance data" in STUDY_AID_NOTICE
