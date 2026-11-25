import hashlib
from typing import Any

import pydantic
import pytest

from hangar.core.chunks import Chunk, ChunksMeta, chunk_id, chunker_id
from hangar.core.config import ChunkingConfig
from tests.builders import CHUNKER_ID, DOCUMENT_ID, chunk


def validated_chunk(**changes: Any) -> Chunk:
    """
    Validate a chunk of "hello" at offsets 10 to 15, with the given fields changed.
    """
    fields = chunk("hello", start=10).model_dump() | changes

    return Chunk.model_validate(fields)


def chunking(**changes: Any) -> ChunkingConfig:
    fields: dict[str, Any] = {
        "type": "fixed_tokens",
        "size": 512,
        "overlap": 0,
        "tokenizer": "embedder",
    }
    fields.update(changes)

    return ChunkingConfig.model_validate(fields)


def test_chunk_id_is_a_short_hash_of_document_chunker_and_offsets() -> None:
    expected = hashlib.sha256(b"faa-h-8083-31b|fixed512|0|2048").hexdigest()[:16]

    assert chunk_id("faa-h-8083-31b", "fixed512", 0, 2048) == expected


@pytest.mark.parametrize(
    "other",
    [
        ("other-handbook", "fixed512", 0, 2048),
        ("faa-h-8083-31b", "fixed256", 0, 2048),
        ("faa-h-8083-31b", "fixed512", 1, 2048),
        ("faa-h-8083-31b", "fixed512", 0, 2049),
    ],
)
def test_chunk_id_changes_with_each_part(other: tuple[str, str, int, int]) -> None:
    assert chunk_id(*other) != chunk_id("faa-h-8083-31b", "fixed512", 0, 2048)


def test_chunker_id_names_the_size() -> None:
    assert chunker_id(chunking()) == "fixed512"


def test_chunker_id_names_the_overlap_when_there_is_one() -> None:
    assert chunker_id(chunking(size=256, overlap=32)) == "fixed256-o32"


def test_a_valid_chunk_survives_a_json_round_trip() -> None:
    original = validated_chunk()

    assert Chunk.model_validate_json(original.model_dump_json()) == original


def test_a_chunk_must_hold_at_least_one_character() -> None:
    with pytest.raises(pydantic.ValidationError, match="must come after start"):
        validated_chunk(id=chunk_id(DOCUMENT_ID, CHUNKER_ID, 10, 10), end=10, text="")


def test_a_chunk_end_cannot_come_before_its_start() -> None:
    with pytest.raises(pydantic.ValidationError, match="must come after start"):
        validated_chunk(id=chunk_id(DOCUMENT_ID, CHUNKER_ID, 10, 5), end=5)


def test_a_chunk_text_must_match_its_offsets() -> None:
    with pytest.raises(pydantic.ValidationError, match="has 4 characters"):
        validated_chunk(text="hell")


def test_a_chunk_id_must_derive_from_its_content_and_location() -> None:
    with pytest.raises(pydantic.ValidationError, match="should have the ID"):
        validated_chunk(id="0123456789abcdef")


def test_a_chunk_covers_at_least_one_passage() -> None:
    with pytest.raises(pydantic.ValidationError, match="passages"):
        validated_chunk(passages=[])


def meta(**changes: Any) -> ChunksMeta:
    fields: dict[str, Any] = {
        "snapshot": "c1",
        "chunker_id": CHUNKER_ID,
        "config_hash": "a" * 64,
        "tokenizer": {"model": "BAAI/bge-m3", "revision": "b" * 40},
        "parsed_files": {DOCUMENT_ID: "c" * 64},
        "chunks": 3,
        "tokens": 1200,
    }
    fields.update(changes)

    return ChunksMeta.model_validate(fields)


def test_chunks_meta_counts_the_documents_it_read() -> None:
    assert meta().documents == 1


def test_chunks_meta_needs_at_least_one_parsed_file() -> None:
    with pytest.raises(pydantic.ValidationError, match="parsed_files"):
        meta(parsed_files={})


def test_chunks_meta_rejects_a_bad_file_hash() -> None:
    with pytest.raises(pydantic.ValidationError, match="parsed_files"):
        meta(parsed_files={DOCUMENT_ID: "not-a-hash"})
