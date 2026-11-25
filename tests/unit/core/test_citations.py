from typing import Any

import pydantic
import pytest

from hangar.core.chunks import PassageRef, chunk_id
from hangar.core.citations import Citation
from hangar.core.parsed import PageLocation

PASSAGE = PassageRef(
    id="faa-h-8083-30b#p323",
    location=PageLocation(page_index=323, page_label="7-79"),
)


def valid_citation(**changes: Any) -> Citation:
    fields: dict[str, Any] = {
        "marker": 1,
        "valid": True,
        "chunk_id": chunk_id("faa-h-8083-30b", "fixed512", 0, 50),
        "document_id": "faa-h-8083-30b",
        "passages": [PASSAGE],
    }
    fields.update(changes)

    return Citation.model_validate(fields)


def invalid_citation(**changes: Any) -> Citation:
    fields: dict[str, Any] = {
        "marker": 9,
        "valid": False,
        "chunk_id": None,
        "document_id": None,
        "passages": [],
    }
    fields.update(changes)

    return Citation.model_validate(fields)


@pytest.mark.parametrize("citation", [valid_citation(), invalid_citation()])
def test_a_citation_survives_a_json_round_trip(citation: Citation) -> None:
    assert Citation.model_validate_json(citation.model_dump_json()) == citation


@pytest.mark.parametrize(
    "changes",
    [{"chunk_id": None}, {"document_id": None}, {"passages": []}],
)
def test_a_valid_citation_names_its_chunk_document_and_passages(
    changes: dict[str, Any],
) -> None:
    with pytest.raises(pydantic.ValidationError, match="valid citation"):
        valid_citation(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"chunk_id": chunk_id("faa-h-8083-30b", "fixed512", 0, 50)},
        {"document_id": "faa-h-8083-30b"},
        {"passages": [PASSAGE]},
    ],
)
def test_an_invalid_citation_points_at_no_source(changes: dict[str, Any]) -> None:
    with pytest.raises(pydantic.ValidationError, match="invalid citation"):
        invalid_citation(**changes)


def test_a_marker_is_not_negative() -> None:
    with pytest.raises(pydantic.ValidationError, match="marker"):
        invalid_citation(marker=-1)
