from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from hangar.core.completions import Completion
from hangar.core.prompts import Message
from hangar.core.records import ScoredChunkRef
from hangar.generation.llm import FAKE_ANSWER, FakeLlmClient
from hangar.generation.prompt import load_prompt_template
from hangar.pipelines.answer import AnswerPipeline
from hangar.pipelines.config import load_pipeline_config
from hangar.retrieval.retriever import FixedRetriever
from tests.builders import RUN_ID, chunk, document_spec, page, section

ROOT = Path(__file__).resolve().parents[3]
CONFIG = load_pipeline_config(ROOT / "configs" / "pipelines" / "v0.yaml")
TEMPLATE = load_prompt_template(ROOT / "prompts", CONFIG.generation.prompt)

HANDBOOK = document_spec()
STANDARD = document_spec(id="tc-std-571", authority="TC", type="standard")
DOCUMENTS = {HANDBOOK.id: HANDBOOK, STANDARD.id: STANDARD}
CHUNKS = [
    chunk("Replace the ELT battery.", passages=[page(323, document_id=HANDBOOK.id)]),
    chunk("Record the date.", passages=[section("571.10")]),
]
QUESTION = "When is the ELT battery replaced?"


class RecordingLlm(FakeLlmClient):
    """The fake client, keeping the parameters of each call."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[int, float, int]] = []

    def complete(
        self,
        messages: Sequence[Message],
        *,
        temperature: float,
        max_output_tokens: int,
    ) -> Completion:
        self.calls.append((len(messages), temperature, max_output_tokens))

        return super().complete(
            messages, temperature=temperature, max_output_tokens=max_output_tokens
        )


class CutOffLlm(FakeLlmClient):
    """The fake client, as if every answer hit the output token limit."""

    def complete(
        self,
        messages: Sequence[Message],
        *,
        temperature: float,
        max_output_tokens: int,
    ) -> Completion:
        completion = super().complete(
            messages, temperature=temperature, max_output_tokens=max_output_tokens
        )

        return completion.model_copy(update={"finish_reason": "length"})


def ticks(*seconds: float) -> Callable[[], float]:
    """A clock that gives each number of seconds in turn."""
    times = iter(seconds)

    return lambda: next(times)


def pipeline(
    llm: FakeLlmClient | None = None, clock: Callable[[], float] | None = None
) -> AnswerPipeline:
    return AnswerPipeline(
        FixedRetriever(CHUNKS),
        TEMPLATE,
        DOCUMENTS,
        llm or FakeLlmClient(),
        CONFIG,
        clock=clock or ticks(0.0, 0.0, 0.0, 0.0),
    )


def test_the_record_keeps_the_question_its_run_and_what_was_retrieved() -> None:
    record = pipeline().answer(QUESTION, RUN_ID)

    assert record.run_id == RUN_ID
    assert record.question_id is None
    assert record.question == QUESTION
    assert record.prompt_version == "answer-v0"
    assert record.scored_chunks == tuple(
        ScoredChunkRef.of(found) for found in FixedRetriever(CHUNKS).retrieve(QUESTION)
    )


def test_a_seed_question_keeps_its_id() -> None:
    record = pipeline().answer(QUESTION, RUN_ID, question_id="q-0001")

    assert record.question_id == "q-0001"


def test_the_record_holds_no_chunk_text() -> None:
    record_json = pipeline().answer(QUESTION, RUN_ID).model_dump_json()

    for retrieved in CHUNKS:
        assert retrieved.text not in record_json


def test_the_model_gets_the_rendered_prompt_with_the_configured_parameters() -> None:
    llm = RecordingLlm()

    record = pipeline(llm).answer(QUESTION, RUN_ID)

    generation = CONFIG.generation
    assert llm.calls == [(2, generation.temperature, generation.max_output_tokens)]
    assert record.completion.text == FAKE_ANSWER


def test_each_marker_traces_to_its_document_and_pages_or_sections() -> None:
    record = pipeline().answer(QUESTION, RUN_ID)

    assert [(c.marker, c.valid, c.document_id) for c in record.citations] == [
        (1, True, HANDBOOK.id),
        (2, True, STANDARD.id),
    ]
    assert record.citations[0].passages == CHUNKS[0].passages
    assert record.citations[1].passages == CHUNKS[1].passages


def test_a_marker_outside_the_sources_is_kept_as_invalid() -> None:
    record = pipeline(FakeLlmClient("Replace it [1], then test it [6].")).answer(
        QUESTION, RUN_ID
    )

    assert [(c.marker, c.valid) for c in record.citations] == [(1, True), (6, False)]


def test_retrieval_and_generation_are_timed_separately() -> None:
    record = pipeline(clock=ticks(10.0, 10.25, 11.0, 12.75)).answer(QUESTION, RUN_ID)

    assert record.timings.retrieval_seconds == pytest.approx(0.25)
    assert record.timings.generation_seconds == pytest.approx(1.75)


def test_the_tokens_are_priced_with_the_configured_model() -> None:
    record = pipeline().answer(QUESTION, RUN_ID)

    prices = CONFIG.prices[CONFIG.generation.model].list_price
    tokens = record.completion
    expected = (
        tokens.input_tokens * prices.input_usd_per_million
        + tokens.output_tokens * prices.output_usd_per_million
    ) / 1_000_000
    assert record.cost.free_tier_usd == 0.0
    assert record.cost.list_price_usd == pytest.approx(expected)
    assert expected > 0


def test_a_finished_answer_says_it_stopped() -> None:
    assert pipeline().answer(QUESTION, RUN_ID).finish_reason == "stop"


def test_a_cut_off_answer_can_be_told_apart() -> None:
    assert pipeline(CutOffLlm()).answer(QUESTION, RUN_ID).finish_reason == "length"
