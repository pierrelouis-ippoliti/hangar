from typing import Any

import pytest

from hangar.core.config import NormalisationConfig, ParseChecksConfig
from hangar.core.corpus import DocumentSpec
from hangar.core.parsed import (
    PageLocation,
    ParsedDocument,
    ParserInfo,
    ParseWarning,
    SectionLocation,
)
from hangar.parsing.assemble import TextPart, assemble
from hangar.parsing.report import (
    ParseCheckError,
    ParseReport,
    check_report,
    document_report,
)

NORMALISATION = NormalisationConfig(unicode_form="NFKC", collapse_whitespace=True)
FAKE_SHA256 = "0123456789abcdef" * 4
CHECKS = ParseChecksConfig(
    min_characters=10,
    min_sections=1,
    max_empty_page_share=0.25,
    max_garbled_page_share=0.25,
)


def spec(document_id: str, document_format: str) -> DocumentSpec:
    return DocumentSpec.model_validate(
        {
            "id": document_id,
            "title": "Example",
            "authority": "TC",
            "type": "advisory_circular",
            "language": "en",
            "source_url": "https://example.org/page",
            "official_url": "https://example.org/page",
            "format": document_format,
            "edition": "Issue 01",
            "content_date": "2024-01-01",
            "page_modified_date": "2024-01-01",
            "retrieved_on": "2026-11-04",
            "status": "active",
            "sha256": FAKE_SHA256,
            "reuse_note": "Made up for tests.",
        }
    )


def parsed(
    document_id: str, parts: list[TextPart], warnings: tuple[dict[str, Any], ...] = ()
) -> ParsedDocument:
    text, passages = assemble(document_id, parts, NORMALISATION)

    return ParsedDocument(
        document_id=document_id,
        source_sha256=FAKE_SHA256,
        parser=ParserInfo(name="example", version="1.0"),
        text=text,
        passages=passages,
        warnings=tuple(ParseWarning.model_validate(w) for w in warnings),
    )


def pdf(
    document_id: str, pages: list[str], garbled: tuple[int, ...] = ()
) -> ParsedDocument:
    parts = [
        TextPart(PageLocation(page_index=i, page_label=None), text)
        for i, text in enumerate(pages, start=1)
    ]
    warnings = tuple(
        {"code": "garbled_page", "passage_id": f"{document_id}#p{i}", "message": "x"}
        for i in garbled
    )

    return parsed(document_id, parts, warnings)


def sections(document_id: str, labels: list[str | None]) -> ParsedDocument:
    parts = [
        TextPart(SectionLocation(label=label, heading_path=()), f"text of {label}")
        for label in labels
    ]

    return parsed(document_id, parts)


def test_pdf_report_counts_pages_empty_pages_and_garbled_pages() -> None:
    report = document_report(
        spec("handbook", "pdf"),
        pdf("handbook", ["first page", "", "third page", "fourth"], garbled=(3,)),
    )

    assert report.document_id == "handbook"
    assert report.format == "pdf"
    assert report.characters == len("first page\n\nthird page\n\nfourth")
    assert report.passages == 4
    assert (report.pages, report.empty_pages, report.garbled_pages) == (4, 1, 1)
    assert report.sections is None
    assert [w.code for w in report.warnings] == ["garbled_page"]


def test_section_report_counts_numbered_sections_but_not_the_front_matter() -> None:
    report = document_report(spec("ac", "html"), sections("ac", [None, "1.0", "1.1"]))

    assert report.sections == 2
    assert report.passages == 3
    assert (report.pages, report.empty_pages, report.garbled_pages) == (
        None,
        None,
        None,
    )


def test_report_records_the_parser_and_the_source_hash() -> None:
    report = document_report(spec("ac", "html"), sections("ac", ["1.0"]))

    assert report.parser == ParserInfo(name="example", version="1.0")
    assert report.source_sha256 == FAKE_SHA256


def report_of(*documents: tuple[DocumentSpec, ParsedDocument]) -> ParseReport:
    return ParseReport(
        snapshot="c1",
        config_hash=FAKE_SHA256,
        documents=tuple(document_report(d, p) for d, p in documents),
    )


def test_documents_within_the_thresholds_pass() -> None:
    report = report_of(
        (spec("handbook", "pdf"), pdf("handbook", ["a long first page"] * 4)),
        (spec("ac", "html"), sections("ac", [None, "1.0"])),
    )

    assert check_report(report, CHECKS) == []


def test_a_short_document_fails_with_its_character_count() -> None:
    report = report_of((spec("tiny", "pdf"), pdf("tiny", ["short"])))

    assert check_report(report, CHECKS) == [
        "tiny: 5 characters, fewer than the minimum of 10"
    ]


def test_a_page_without_sections_fails_the_section_minimum() -> None:
    report = report_of((spec("notice", "html"), sections("notice", [None])))

    assert check_report(report, CHECKS) == [
        "notice: 0 numbered sections, fewer than the minimum of 1"
    ]


def test_too_many_empty_or_garbled_pages_fail_with_their_share() -> None:
    report = report_of(
        (
            spec("handbook", "pdf"),
            pdf("handbook", ["page one text", "", "", "page four"], garbled=(1, 4)),
        )
    )

    assert check_report(report, CHECKS) == [
        "handbook: 2 of 4 pages are empty (50.0%), more than the maximum of 25.0%",
        "handbook: 2 of 4 pages are garbled (50.0%), more than the maximum of 25.0%",
    ]


def test_every_failing_document_is_reported() -> None:
    report = report_of(
        (spec("tiny", "pdf"), pdf("tiny", ["short"])),
        (spec("notice", "html"), sections("notice", [None])),
    )

    assert [problem.split(":")[0] for problem in check_report(report, CHECKS)] == [
        "tiny",
        "notice",
    ]


def test_check_error_lists_one_problem_per_line() -> None:
    error = ParseCheckError(["tiny: too short", "notice: no sections"])

    assert error.problems == ("tiny: too short", "notice: no sections")
    assert str(error).splitlines() == [
        "2 parse checks failed:",
        "tiny: too short",
        "notice: no sections",
    ]


def test_report_survives_a_json_round_trip() -> None:
    report = report_of((spec("handbook", "pdf"), pdf("handbook", ["text", ""])))

    assert ParseReport.model_validate_json(report.model_dump_json()) == report


def test_report_config_hash_must_be_a_sha256() -> None:
    with pytest.raises(ValueError):
        ParseReport(snapshot="c1", config_hash="abc", documents=())
