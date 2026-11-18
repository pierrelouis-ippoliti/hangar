from typing import Any

import pydantic
import pytest

from hangar.core.config import EmbeddingConfig
from hangar.core.vectors import EmbedderInfo, VectorRecord, VectorsMeta, embedder_id

CHUNK_ID = "0123456789abcdef"


def embedding(**changes: Any) -> EmbeddingConfig:
    fields: dict[str, Any] = {
        "type": "sentence_transformers",
        "model": "BAAI/bge-m3",
        "revision": "5617a9f61b028005a4858fdac845db406aefb181",
        "output": "dense",
        "batch_size": 16,
        "normalize": True,
    }
    fields.update(changes)

    return EmbeddingConfig.model_validate(fields)


def meta(**changes: Any) -> VectorsMeta:
    fields: dict[str, Any] = {
        "snapshot": "c1",
        "chunker_id": "fixed512",
        "embedder_id": "bge-m3-dense",
        "config_hash": "a" * 64,
        "embedder": {
            "model_id": "BAAI/bge-m3",
            "revision": "b" * 40,
            "dimension": 1024,
            "normalized": True,
        },
        "chunks_sha256": "c" * 64,
        "vectors": 3,
    }
    fields.update(changes)

    return VectorsMeta.model_validate(fields)


def test_embedder_id_names_the_model_and_its_output() -> None:
    assert embedder_id(embedding()) == "bge-m3-dense"


def test_embedder_id_is_lower_case_and_leaves_out_the_organisation() -> None:
    assert embedder_id(embedding(model="intfloat/E5-Large")) == "e5-large-dense"


def test_a_vector_record_survives_a_json_round_trip() -> None:
    record = VectorRecord(
        chunk_id=CHUNK_ID, model_id="BAAI/bge-m3", revision="b" * 40, vector=(0.6, 0.8)
    )

    assert VectorRecord.model_validate_json(record.model_dump_json()) == record


def test_a_vector_record_needs_a_chunk_id() -> None:
    with pytest.raises(pydantic.ValidationError, match="chunk_id"):
        VectorRecord(chunk_id="x", model_id="m", revision="r", vector=(1.0,))


def test_a_vector_record_needs_a_vector() -> None:
    with pytest.raises(pydantic.ValidationError, match="vector"):
        VectorRecord(chunk_id=CHUNK_ID, model_id="m", revision="r", vector=())


def test_vectors_meta_accepts_a_valid_record() -> None:
    assert meta().embedder == EmbedderInfo(
        model_id="BAAI/bge-m3", revision="b" * 40, dimension=1024, normalized=True
    )


def test_vectors_meta_rejects_a_bad_chunks_hash() -> None:
    with pytest.raises(pydantic.ValidationError, match="chunks_sha256"):
        meta(chunks_sha256="not-a-hash")
