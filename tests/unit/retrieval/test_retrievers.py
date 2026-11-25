import pytest
from qdrant_client import QdrantClient

from hangar.embedding.embedder import HashEmbedder
from hangar.indexing.qdrant import QdrantIndex
from hangar.retrieval.dense import DenseRetriever
from hangar.retrieval.retriever import FixedRetriever
from tests.builders import consecutive_chunks

TEXTS = [
    "torque the propeller bolts ",
    "safety wire the turnbuckle ",
    "sign the maintenance release ",
    "inspect the fuel filter ",
    "check the tire pressure",
]
CHUNKS = consecutive_chunks(TEXTS)


def dense(top_k: int) -> DenseRetriever:
    embedder = HashEmbedder(dimension=16)
    index = QdrantIndex(QdrantClient(":memory:"), "c1__fixed512__test")
    index.recreate(dimension=16)
    index.upsert(CHUNKS, embedder.embed_documents([c.text for c in CHUNKS]))

    return DenseRetriever(embedder, index, top_k=top_k)


def test_a_chunk_s_exact_text_finds_it_first() -> None:
    results = dense(top_k=3).retrieve(TEXTS[2])

    assert results[0].chunk == CHUNKS[2]
    assert results[0].score == pytest.approx(1.0)


def test_dense_results_are_the_top_k_ranked_from_1_best_first() -> None:
    results = dense(top_k=3).retrieve("how tight should the bolts be")

    assert len(results) == 3
    assert [r.rank for r in results] == [1, 2, 3]
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    assert {r.retriever_id for r in results} == {"dense"}


def test_dense_returns_every_chunk_when_there_are_fewer_than_k() -> None:
    assert len(dense(top_k=10).retrieve("anything")) == len(CHUNKS)


def test_the_fixed_retriever_returns_its_chunks_in_order_whatever_the_question() -> (
    None
):
    retriever = FixedRetriever(CHUNKS[:2])

    for question in ["torque", "something else"]:
        results = retriever.retrieve(question)

        assert [r.chunk for r in results] == CHUNKS[:2]
        assert [r.rank for r in results] == [1, 2]
        assert {r.retriever_id for r in results} == {"fixed"}
