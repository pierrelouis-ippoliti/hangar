from typing import Any

import pydantic
import pytest

from hangar.core.chunks import Chunk, PassageRef, chunk_id
from hangar.core.parsed import PageLocation
from hangar.core.retrieval import ScoredChunk

TEXT = "torque the bolt"
CHUNK = Chunk(
    id=chunk_id("example-handbook", "fixed512", 0, len(TEXT)),
    document_id="example-handbook",
    chunker_id="fixed512",
    start=0,
    end=len(TEXT),
    text=TEXT,
    token_count=3,
    passages=[
        PassageRef(
            id="example-handbook#p1",
            location=PageLocation(page_index=1, page_label=None),
        )
    ],
)


def scored(**changes: Any) -> ScoredChunk:
    fields: dict[str, Any] = {
        "chunk": CHUNK,
        "score": 0.71,
        "rank": 1,
        "retriever_id": "dense",
    }
    fields.update(changes)

    return ScoredChunk.model_validate(fields)


def test_a_scored_chunk_survives_a_json_round_trip() -> None:
    original = scored()

    assert ScoredChunk.model_validate_json(original.model_dump_json()) == original


def test_ranks_start_at_1() -> None:
    with pytest.raises(pydantic.ValidationError, match="rank"):
        scored(rank=0)


def test_a_scored_chunk_names_its_retriever() -> None:
    with pytest.raises(pydantic.ValidationError, match="retriever_id"):
        scored(retriever_id="")
