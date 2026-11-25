import pydantic
import pytest

from hangar.core.retrieval import ScoredChunk
from tests.builders import scored


def test_a_scored_chunk_survives_a_json_round_trip() -> None:
    original = scored()

    assert ScoredChunk.model_validate_json(original.model_dump_json()) == original


def test_ranks_start_at_1() -> None:
    with pytest.raises(pydantic.ValidationError, match="rank"):
        scored(rank=0)


def test_a_scored_chunk_names_its_retriever() -> None:
    with pytest.raises(pydantic.ValidationError, match="retriever_id"):
        scored(retriever_id="")
