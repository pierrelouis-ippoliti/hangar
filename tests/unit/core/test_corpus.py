import datetime
from typing import Any

import pydantic
import pytest

from hangar.core.corpus import parse_manifest
from hangar.core.errors import ConfigError

SOURCE = "corpus/test-manifest.yaml"
FAKE_SHA256 = "0123456789abcdef" * 4


def document(**changes: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": "example-handbook",
        "title": "Example Handbook",
        "authority": "FAA",
        "type": "handbook",
        "language": "en",
        "source_url": "https://example.org/example-handbook.pdf",
        "format": "pdf",
        "edition": "B",
        "content_date": datetime.date(2023, 1, 1),
        "page_modified_date": datetime.date(2024, 6, 1),
        "retrieved_on": datetime.date(2026, 11, 4),
        "status": "active",
        "sha256": FAKE_SHA256,
        "reuse_note": "Public domain.",
    }
    entry.update(changes)
    return entry


def manifest(*documents: dict[str, Any]) -> dict[str, Any]:
    return {"snapshot": "c1", "documents": list(documents) or [document()]}


def problem_fields(data: object) -> list[str | None]:
    with pytest.raises(ConfigError) as error_info:
        parse_manifest(data, SOURCE)
    assert error_info.value.source == SOURCE
    return [p.field for p in error_info.value.problems]


def test_valid_manifest_gives_typed_document_specs() -> None:
    parsed = parse_manifest(manifest(), SOURCE)

    assert parsed.snapshot == "c1"
    [spec] = parsed.documents
    assert spec.id == "example-handbook"
    assert spec.authority == "FAA"
    assert spec.type == "handbook"
    assert str(spec.source_url) == "https://example.org/example-handbook.pdf"
    assert spec.content_date == datetime.date(2023, 1, 1)
    assert spec.page_modified_date == datetime.date(2024, 6, 1)
    assert spec.sha256 == FAKE_SHA256


def test_dates_written_as_text_are_accepted() -> None:
    parsed = parse_manifest(manifest(document(retrieved_on="2026-11-04")), SOURCE)

    assert parsed.documents[0].retrieved_on == datetime.date(2026, 11, 4)


def test_edition_written_as_a_number_is_kept_as_text() -> None:
    # YAML reads `edition: 2023` as an integer.
    parsed = parse_manifest(manifest(document(edition=2023)), SOURCE)

    assert parsed.documents[0].edition == "2023"


def test_document_specs_cannot_be_changed() -> None:
    spec = parse_manifest(manifest(), SOURCE).documents[0]

    with pytest.raises(pydantic.ValidationError):
        spec.status = "cancelled"  # type: ignore[misc]


@pytest.mark.parametrize(
    "authority, doc_type", [("TC", "regulation"), ("TC", "standard")]
)
def test_known_authorities_and_types_are_accepted(
    authority: str, doc_type: str
) -> None:
    entry = document(authority=authority, type=doc_type)

    assert parse_manifest(manifest(entry), SOURCE).documents[0].type == doc_type


def test_advisory_circular_html_document_is_accepted() -> None:
    entry = document(
        id="tc-ac-000-001", authority="TC", type="advisory_circular", format="html"
    )

    assert parse_manifest(manifest(entry), SOURCE).documents[0].format == "html"


@pytest.mark.parametrize(
    "field, value",
    [
        ("id", "Example Handbook"),
        ("id", "example_handbook"),
        ("id", "-example"),
        ("id", "example--handbook"),
        ("title", ""),
        ("authority", "EASA"),
        ("type", "manual"),
        ("language", "english"),
        ("source_url", "not a url"),
        ("format", "docx"),
        ("edition", ""),
        ("content_date", "1 January 2023"),
        ("page_modified_date", None),
        ("retrieved_on", "yesterday"),
        ("status", "withdrawn"),
        ("sha256", FAKE_SHA256[:-1]),
        ("sha256", FAKE_SHA256.upper()),
        ("sha256", "g" * 64),
        ("reuse_note", ""),
    ],
)
def test_invalid_value_error_names_the_document_field(field: str, value: Any) -> None:
    data = manifest(document(id="first-document"), document(**{field: value}))

    assert problem_fields(data) == [f"documents[1].{field}"]


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "title",
        "authority",
        "type",
        "language",
        "source_url",
        "format",
        "edition",
        "content_date",
        "page_modified_date",
        "retrieved_on",
        "status",
        "sha256",
        "reuse_note",
    ],
)
def test_every_field_is_required(field: str) -> None:
    entry = document()
    del entry[field]

    assert problem_fields(manifest(entry)) == [f"documents[0].{field}"]


def test_unknown_field_is_rejected_so_typos_are_caught() -> None:
    assert problem_fields(manifest(document(sha_256=FAKE_SHA256))) == [
        "documents[0].sha_256"
    ]


def test_duplicate_id_error_names_the_repeated_entry() -> None:
    data = manifest(
        document(id="example-handbook"),
        document(id="example-standard"),
        document(id="example-handbook"),
    )

    with pytest.raises(ConfigError) as error_info:
        parse_manifest(data, SOURCE)

    [problem] = error_info.value.problems
    assert problem.field == "documents[2].id"
    assert "documents[0]" in problem.message


@pytest.mark.parametrize("snapshot", ["C1", "1", "c", "c1-draft"])
def test_snapshot_must_look_like_c_and_a_number(snapshot: str) -> None:
    data = manifest()
    data["snapshot"] = snapshot

    assert problem_fields(data) == ["snapshot"]


def test_manifest_needs_at_least_one_document() -> None:
    assert problem_fields({"snapshot": "c1", "documents": []}) == ["documents"]


@pytest.mark.parametrize("data", [None, [], "c1"])
def test_content_that_is_not_a_mapping_is_rejected(data: object) -> None:
    assert problem_fields(data) == [None]


def test_active_documents_leave_out_cancelled_ones() -> None:
    parsed = parse_manifest(
        manifest(
            document(id="kept-first"),
            document(id="cancelled-one", status="cancelled"),
            document(id="kept-second"),
        ),
        SOURCE,
    )

    assert [d.id for d in parsed.active_documents()] == ["kept-first", "kept-second"]
