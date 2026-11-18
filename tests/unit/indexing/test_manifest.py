from typing import Any

import pydantic
import pytest

from hangar.indexing.manifest import IndexManifest


def manifest(**changes: Any) -> IndexManifest:
    fields: dict[str, Any] = {
        "collection": "c1__fixed512__bge-m3-dense",
        "snapshot": "c1",
        "chunker_id": "fixed512",
        "embedder_id": "bge-m3-dense",
        "embedder": {
            "model_id": "BAAI/bge-m3",
            "revision": "b" * 40,
            "dimension": 1024,
            "normalized": True,
        },
        "distance": "cosine",
        "points": 3627,
        "qdrant_version": "1.20.0",
        "config_hash": "a" * 64,
        "chunks_sha256": "c" * 64,
        "vectors_sha256": "d" * 64,
    }
    fields.update(changes)

    return IndexManifest.model_validate(fields)


def test_a_manifest_survives_a_json_round_trip() -> None:
    original = manifest()

    assert IndexManifest.model_validate_json(original.model_dump_json()) == original


def test_a_manifest_has_no_creation_time() -> None:
    with pytest.raises(pydantic.ValidationError, match="created_at"):
        manifest(created_at="2026-11-18T10:00:00Z")


def test_a_manifest_rejects_a_bad_input_hash() -> None:
    with pytest.raises(pydantic.ValidationError, match="vectors_sha256"):
        manifest(vectors_sha256="not-a-hash")
