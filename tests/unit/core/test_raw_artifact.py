import datetime

import pydantic
import pytest

from hangar.core.corpus import DocumentSpec, RawArtifact, raw_artifact_id

FAKE_SHA256 = "0123456789abcdef" * 4
FETCHED_AT = datetime.datetime(2026, 11, 5, 9, 30, tzinfo=datetime.UTC)


def spec(document_id: str, document_format: str) -> DocumentSpec:
    return DocumentSpec.model_validate(
        {
            "id": document_id,
            "title": "Example",
            "authority": "TC",
            "type": "advisory_circular",
            "language": "en",
            "source_url": "https://example.org/page",
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


def artifact(**changes: object) -> RawArtifact:
    fields: dict[str, object] = {
        "id": "faa-h-8083-31b.pdf",
        "document_id": "faa-h-8083-31b",
        "path": "data/raw/faa-h-8083-31b.pdf",
        "sha256": FAKE_SHA256,
        "size_bytes": 1024,
        "fetched_at": FETCHED_AT,
        "etag": '"abc"',
        "last_modified": "Fri, 21 Jul 2023 14:02:11 GMT",
    }
    fields.update(changes)
    return RawArtifact.model_validate(fields)


@pytest.mark.parametrize(
    ("document_id", "document_format", "expected"),
    [
        ("faa-h-8083-31b", "pdf", "faa-h-8083-31b.pdf"),
        ("car-sor-96-433", "xml", "car-sor-96-433.xml"),
        ("tc-ac-571-002", "html", "tc-ac-571-002.html"),
    ],
)
def test_raw_artifact_id_is_the_document_id_plus_its_extension(
    document_id: str, document_format: str, expected: str
) -> None:
    assert raw_artifact_id(spec(document_id, document_format)) == expected


def test_raw_artifact_survives_a_json_round_trip() -> None:
    record = artifact()

    assert RawArtifact.model_validate_json(record.model_dump_json()) == record


def test_raw_artifact_validators_may_be_missing() -> None:
    record = artifact(etag=None, last_modified=None)

    assert (record.etag, record.last_modified) == (None, None)


@pytest.mark.parametrize(
    "changes",
    [
        {"sha256": "not-a-hash"},
        {"size_bytes": -1},
        {"fetched_at": datetime.datetime(2026, 11, 5, 9, 30)},
    ],
    ids=["bad hash", "negative size", "time without a time zone"],
)
def test_raw_artifact_rejects_invalid_values(changes: dict[str, object]) -> None:
    with pytest.raises(pydantic.ValidationError):
        artifact(**changes)
