import math

import pytest

from hangar.embedding.embedder import HashEmbedder


def length(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def test_the_same_text_always_gives_the_same_vector() -> None:
    first = HashEmbedder(dimension=8).embed_documents(["torque the bolt"])
    second = HashEmbedder(dimension=8).embed_documents(["torque the bolt"])

    assert first == second


def test_different_texts_give_different_vectors() -> None:
    vectors = HashEmbedder(dimension=8).embed_documents(["torque", "safety wire"])

    assert vectors[0] != vectors[1]


def test_vectors_have_the_reported_dimension_and_unit_length() -> None:
    embedder = HashEmbedder(dimension=40)
    (vector,) = embedder.embed_documents(["torque the bolt"])

    assert embedder.dimension == len(vector) == 40
    assert length(vector) == pytest.approx(1.0)
    assert embedder.normalized


def test_a_query_gets_the_same_vector_as_the_same_document_text() -> None:
    embedder = HashEmbedder(dimension=8)

    assert embedder.embed_query("torque") == embedder.embed_documents(["torque"])[0]


def test_documents_keep_their_order() -> None:
    embedder = HashEmbedder(dimension=8)
    texts = ["a", "b", "c"]

    assert embedder.embed_documents(texts) == [embedder.embed_query(t) for t in texts]


def test_the_hash_embedder_names_itself() -> None:
    embedder = HashEmbedder(dimension=8)

    assert (embedder.model_id, embedder.revision) == ("hash", "1")
