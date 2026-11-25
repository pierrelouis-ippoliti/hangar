"""
One real Mistral call with the v0 prompt.

This test needs MISTRAL_API_KEY in the environment or in .env, and uses one
request of the free tier, so it runs only locally, with `uv run pytest -m
llm tests/llm`. It checks that the API's reply still has the shape the
client reads, and that its token counts are plausible.
"""

from pathlib import Path

import pytest

from hangar.core.chunks import Chunk, PassageRef, chunk_id
from hangar.core.parsed import PageLocation
from hangar.core.retrieval import ScoredChunk
from hangar.corpus.manifest import load_snapshot
from hangar.generation.prompt import load_prompt_template
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.registry import build_llm_client
from hangar.pipelines.settings import load_settings

pytestmark = pytest.mark.llm

ROOT = Path(__file__).resolve().parents[2]
CONFIG = load_pipeline_config(ROOT / "configs" / "pipelines" / "v0.yaml")

DOCUMENT_ID = "faa-h-8083-30b"
SOURCE_TEXT = (
    "Safety wire is installed so that any tendency of the part to loosen "
    "tightens the wire. Never reuse safety wire."
)


def one_source() -> ScoredChunk:
    chunk = Chunk(
        id=chunk_id(DOCUMENT_ID, "fixed512", 0, len(SOURCE_TEXT)),
        document_id=DOCUMENT_ID,
        chunker_id="fixed512",
        start=0,
        end=len(SOURCE_TEXT),
        text=SOURCE_TEXT,
        token_count=len(SOURCE_TEXT.split()),
        passages=[
            PassageRef(
                id=f"{DOCUMENT_ID}#p1",
                location=PageLocation(page_index=1, page_label=None),
            )
        ],
    )

    return ScoredChunk(chunk=chunk, score=1.0, rank=1, retriever_id="fixed")


def test_mistral_answers_the_v0_prompt_with_text_and_token_counts() -> None:
    generation = CONFIG.generation
    documents = {
        document.id: document
        for document in load_snapshot(ROOT / CONFIG.corpus.manifest, "c1")
    }
    template = load_prompt_template(ROOT / "prompts", generation.prompt)
    prompt = template.render("Can safety wire be reused?", [one_source()], documents)
    client = build_llm_client(generation, load_settings(ROOT / ".env").mistral_api_key)

    completion = client.complete(
        prompt.messages,
        temperature=generation.temperature,
        max_output_tokens=generation.max_output_tokens,
    )

    assert completion.text.strip()
    assert completion.model_id == generation.model
    assert completion.finish_reason == "stop"
    # The prompt holds the instructions and one source: well over 100 tokens.
    assert completion.input_tokens > 100
    assert 0 < completion.output_tokens <= generation.max_output_tokens
    assert completion.latency_seconds > 0
