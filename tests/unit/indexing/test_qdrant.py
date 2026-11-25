import math
import socket

import pytest
from qdrant_client import QdrantClient

from hangar.indexing.index import VectorIndexError
from hangar.indexing.qdrant import QdrantIndex
from tests.builders import chunk, page

COLLECTION = "c1__fixed512__test"


def unit(*values: float) -> list[float]:
    length = math.sqrt(sum(v * v for v in values))

    return [v / length for v in values]


CHUNKS = [
    chunk("torque the bolt ", passages=[page(1, "7-12")]),
    chunk("safety wire ", start=16, passages=[page(1, "7-12")]),
    chunk("maintenance release", passages=[page(1, "7-12", document_id="example-ac")]),
]
VECTORS = [unit(1, 0, 0), unit(1, 1, 0), unit(0, 0, 1)]


@pytest.fixture
def index() -> QdrantIndex:
    return QdrantIndex(QdrantClient(":memory:"), COLLECTION)


def filled(index: QdrantIndex) -> QdrantIndex:
    index.recreate(dimension=3)
    index.upsert(CHUNKS, VECTORS)

    return index


def test_recreate_makes_an_empty_collection(index: QdrantIndex) -> None:
    index.recreate(dimension=3)

    assert index.count() == 0
    index.check(dimension=3)


def test_recreate_removes_the_points_of_an_earlier_build(index: QdrantIndex) -> None:
    filled(index)

    index.recreate(dimension=3)

    assert index.count() == 0


def test_upsert_adds_one_point_per_chunk(index: QdrantIndex) -> None:
    assert filled(index).count() == 3


def test_upserting_the_same_chunks_again_adds_no_point(index: QdrantIndex) -> None:
    filled(index).upsert(CHUNKS, VECTORS)

    assert index.count() == 3


def test_a_chunk_s_own_vector_finds_it_first_with_its_whole_payload(
    index: QdrantIndex,
) -> None:
    hits = filled(index).search(VECTORS[1], k=3)

    assert hits[0].chunk == CHUNKS[1]
    assert hits[0].score == pytest.approx(1.0)


def test_search_returns_at_most_k_hits_best_first(index: QdrantIndex) -> None:
    hits = filled(index).search(unit(1, 0.2, 0), k=2)

    assert [h.chunk for h in hits] == [CHUNKS[0], CHUNKS[1]]
    assert hits[0].score > hits[1].score


def test_filters_keep_only_matching_payload_values(index: QdrantIndex) -> None:
    hits = filled(index).search(
        unit(1, 0, 0), k=3, filters={"document_id": "example-ac"}
    )

    assert [h.chunk for h in hits] == [CHUNKS[2]]


def test_check_reports_a_missing_collection(index: QdrantIndex) -> None:
    with pytest.raises(VectorIndexError, match=f"^{COLLECTION}: .*run hangar index"):
        index.check(dimension=3)


def test_check_reports_a_collection_of_another_dimension(index: QdrantIndex) -> None:
    index.recreate(dimension=3)

    with pytest.raises(VectorIndexError, match="vectors of 3 values, not 1024"):
        index.check(dimension=1024)


def test_upsert_refuses_chunks_and_vectors_of_different_lengths(
    index: QdrantIndex,
) -> None:
    index.recreate(dimension=3)

    with pytest.raises(VectorIndexError, match="3 chunks but 2 vectors"):
        index.upsert(CHUNKS, VECTORS[:2])


def test_version_names_the_qdrant_version(index: QdrantIndex) -> None:
    assert index.version() == "1.20.0"


def test_check_says_how_to_start_qdrant_when_it_is_not_running() -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    # No server answers, so skip the client's own version check, which would
    # only warn.
    client = QdrantClient(
        url=f"http://127.0.0.1:{port}", timeout=2, check_compatibility=False
    )

    with pytest.raises(VectorIndexError, match=f"^{COLLECTION}: .*make qdrant-up"):
        QdrantIndex(client, COLLECTION).check(dimension=3)
