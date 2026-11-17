"""
The contract of the BGE-M3 embedder, on the real model.

These tests load BGE-M3 at the pinned revision (2.3 GB, downloaded the
first time), so they run only locally, with `uv run pytest -m model
tests/corpus`. They use the device from HANGAR_DEVICE, so the same tests
check the CPU and the GPU against one reference vector.
"""

import json
import math
from pathlib import Path
from typing import Any

import pytest

from hangar.embedding.embedder import Embedder
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.registry import build_embedder
from hangar.pipelines.settings import Settings

pytestmark = pytest.mark.model

ROOT = Path(__file__).resolve().parents[2]
CONFIG = load_pipeline_config(ROOT / "configs" / "pipelines" / "v0.yaml")
REFERENCE = json.loads(
    (ROOT / "tests" / "fixtures" / "embedding" / "bge-m3-reference.json").read_text()
)


# The model is built through the registry, which imports sentence-transformers
# only when called: importing it here would load torch every time pytest
# collects the tests, even when model tests are deselected.
@pytest.fixture(scope="module")
def embedder() -> Embedder:
    return build_embedder(CONFIG.embedding, Settings().device)


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))

    return dot / math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))


def test_the_reference_was_made_with_the_pinned_model() -> None:
    assert REFERENCE["model"] == CONFIG.embedding.model
    assert REFERENCE["revision"] == CONFIG.embedding.revision


def test_vectors_have_1024_dimensions(embedder: Embedder) -> None:
    (vector,) = embedder.embed_documents(["Safety wire the turnbuckle."])

    assert embedder.dimension == len(vector) == 1024


def test_vectors_have_unit_length(embedder: Embedder) -> None:
    vectors = embedder.embed_documents(["Safety wire the turnbuckle.", "571.10"])

    for vector in vectors:
        assert math.sqrt(sum(x * x for x in vector)) == pytest.approx(1.0, abs=1e-5)


def test_output_matches_the_reference_vector(
    embedder: Embedder,
) -> None:
    (vector,) = embedder.embed_documents([REFERENCE["text"]])
    reference = REFERENCE["vector"]

    # The CPU and the GPU round floats differently, so the match is close,
    # not exact.
    assert cosine(vector, reference) > 0.9999
    assert max(abs(x - y) for x, y in zip(vector, reference, strict=True)) < 1e-3


def test_a_query_is_encoded_like_a_document(
    embedder: Embedder,
) -> None:
    # BGE-M3 has no query prefix, so both give the same vector.
    query = embedder.embed_query(REFERENCE["text"])
    (document,) = embedder.embed_documents([REFERENCE["text"]])

    assert cosine(query, document) > 0.9999


def test_the_registry_builds_the_pinned_model() -> None:
    from hangar.embedding.st_embedder import SentenceTransformerEmbedder

    embedder = build_embedder(CONFIG.embedding, "cpu")

    assert isinstance(embedder, SentenceTransformerEmbedder)
    assert (embedder.model_id, embedder.revision) == (
        CONFIG.embedding.model,
        CONFIG.embedding.revision,
    )
    assert embedder.normalized


def test_loading_the_model_never_fetches_a_safetensors_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The pinned revision has only pytorch_model.bin. transformers then starts
    # a thread that downloads a safetensors copy from a bot's pull request, an
    # unpinned branch of 2.3 GB, unless the conversion is turned off.
    import transformers.modeling_utils

    calls: list[Any] = []
    monkeypatch.setattr(
        transformers.modeling_utils,
        "auto_conversion",
        lambda *args, **kwargs: calls.append(args),
    )

    build_embedder(CONFIG.embedding, "cpu")

    assert calls == []
