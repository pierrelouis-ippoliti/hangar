import datetime

import pydantic
import pytest

from hangar.core.corpus import RawArtifact, raw_artifact_id
from tests.builders import document_spec

FAKE_SHA256 = "0123456789abcdef" * 4
FETCHED_AT = datetime.datetime(2026, 11, 5, 9, 30, tzinfo=datetime.UTC)


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
    assert (
        raw_artifact_id(document_spec(id=document_id, format=document_format))
        == expected
    )


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
        # A naive time on purpose: the model must refuse it.
        {"fetched_at": datetime.datetime(2026, 11, 5, 9, 30)},  # noqa: DTZ001
    ],
    ids=["bad hash", "negative size", "time without a time zone"],
)
def test_raw_artifact_rejects_invalid_values(changes: dict[str, object]) -> None:
    with pytest.raises(pydantic.ValidationError):
        artifact(**changes)
