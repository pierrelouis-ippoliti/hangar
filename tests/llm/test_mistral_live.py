"""
One real Mistral call with the v0 prompt.

This test needs MISTRAL_API_KEY in the environment or in .env, and uses one
request of the free tier, so it runs only locally, with `uv run pytest -m
llm tests/llm`. It checks that the API's reply still has the shape the
client reads, and that its token counts are plausible.
"""

from pathlib import Path

import pytest

from hangar.corpus.manifest import load_snapshot
from hangar.generation.prompt import load_prompt_template
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.registry import build_llm_client
from hangar.pipelines.settings import load_settings
from tests.builders import chunk, scored

pytestmark = pytest.mark.llm

ROOT = Path(__file__).resolve().parents[2]
CONFIG = load_pipeline_config(ROOT / "configs" / "pipelines" / "v0.yaml")

DOCUMENT_ID = "faa-h-8083-30b"
SOURCE_TEXT = (
    "Safety wire is installed so that any tendency of the part to loosen "
    "tightens the wire. Never reuse safety wire."
)


def test_mistral_answers_the_v0_prompt_with_text_and_token_counts() -> None:
    generation = CONFIG.generation
    documents = {
        document.id: document
        for document in load_snapshot(ROOT / CONFIG.corpus.manifest, "c1")
    }
    template = load_prompt_template(ROOT / "prompts", generation.prompt)
    source = scored(chunk(SOURCE_TEXT, document_id=DOCUMENT_ID))
    prompt = template.render("Can safety wire be reused?", [source], documents)
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
