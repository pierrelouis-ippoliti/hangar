"""
The BGE-M3 tokenizer, and the fixed-token chunker on the parsed C1 texts.

These tests download BGE-M3's tokenizer at the pinned revision, and the
last one reads the parsed documents, so they run only locally, after
`hangar parse`, with `uv run pytest -m "model or corpus" tests/corpus`.
"""

from pathlib import Path

import pytest

from hangar.chunking.fixed import FixedTokenChunker
from hangar.chunking.hf_tokenizer import HfTokenCounter
from hangar.core.parsed import ParsedFile
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.registry import build_chunker
from hangar.pipelines.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
CONFIG = load_pipeline_config(ROOT / "configs" / "pipelines" / "v0.yaml")


@pytest.fixture(scope="module")
def counter() -> HfTokenCounter:
    return HfTokenCounter.from_hub(CONFIG.embedding.model, CONFIG.embedding.revision)


@pytest.mark.model
def test_bge_m3_tokens_and_their_starts(counter: HfTokenCounter) -> None:
    # BGE-M3 splits "hello world" into "▁hell", "o" and "▁world"; a token
    # includes the space before it.
    assert counter.count("hello world") == 3
    assert counter.token_starts("hello world") == [0, 4, 5]


@pytest.mark.model
def test_the_registry_builds_the_fixed_512_chunker() -> None:
    chunker = build_chunker(CONFIG.chunking, CONFIG.embedding)

    assert isinstance(chunker, FixedTokenChunker)
    assert chunker.id == "fixed512"


@pytest.mark.model
@pytest.mark.corpus
def test_no_c1_chunk_is_over_512_tokens(counter: HfTokenCounter) -> None:
    folder = Settings().data_dir / "parsed" / "c1"

    if not folder.is_dir():
        pytest.skip(f"{folder} doesn't exist; run hangar parse first")

    chunker = FixedTokenChunker(counter, CONFIG.chunking)

    for path in sorted(folder.glob("*.json")):
        document = ParsedFile.model_validate_json(path.read_text()).document
        chunks = chunker.chunk(document)

        assert max(c.token_count for c in chunks) <= 512, document.document_id
        assert "".join(c.text for c in chunks) == document.text
