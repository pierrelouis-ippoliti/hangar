import json
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from hangar.core.costs import Cost
from hangar.core.records import RunRecord, RunTotals, StageTimings, run_totals
from tests.builders import STARTED_AT, answer_record, completion, run_record


def test_an_answer_record_holds_every_field_of_the_issue() -> None:
    written = json.loads(answer_record().model_dump_json())

    assert set(written) == {
        "run_id",
        "question_id",
        "question",
        "scored_chunks",
        "prompt_version",
        "completion",
        "citations",
        "timings",
        "cost",
    }
    assert set(written["timings"]) == {"retrieval_seconds", "generation_seconds"}


def test_an_answer_record_reads_back_from_its_json() -> None:
    record = answer_record(question_id="q-0001")

    assert type(record).model_validate_json(record.model_dump_json()) == record


def test_a_run_record_holds_every_field_of_the_issue() -> None:
    written = json.loads(run_record().model_dump_json())

    assert set(written) == {
        "run_id",
        "config_hash",
        "code",
        "snapshot",
        "models",
        "started_at",
        "ended_at",
        "totals",
    }
    assert set(written["code"]) == {"commit", "dirty"}
    assert set(written["models"]) == {
        "embedding_model",
        "embedding_revision",
        "generation_model",
    }
    assert set(written["totals"]) == {
        "answers",
        "input_tokens",
        "output_tokens",
        "cost",
        "retrieval_seconds",
        "generation_seconds",
    }


def test_a_run_record_reads_back_from_its_json() -> None:
    record = run_record()

    assert RunRecord.model_validate_json(record.model_dump_json()) == record


def test_a_run_outside_a_git_checkout_has_no_code_version() -> None:
    assert run_record(code=None).code is None


def test_a_run_cannot_end_before_it_starts() -> None:
    with pytest.raises(ValidationError, match="ends before it starts"):
        run_record(ended_at=STARTED_AT - timedelta(seconds=1))


def test_run_times_must_have_a_time_zone() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        run_record(started_at=datetime(2026, 11, 25, 12, 0, 0))  # noqa: DTZ001


def test_run_totals_add_tokens_costs_and_stage_timings() -> None:
    answers = [
        answer_record(
            completion=completion(input_tokens=900, output_tokens=100),
            timings=StageTimings(retrieval_seconds=0.25, generation_seconds=1.5),
            cost=Cost(free_tier_usd=0.0, list_price_usd=0.0002),
        ),
        answer_record(
            completion=completion(input_tokens=1100, output_tokens=300),
            timings=StageTimings(retrieval_seconds=0.5, generation_seconds=2.0),
            cost=Cost(free_tier_usd=0.0, list_price_usd=0.0004),
        ),
    ]

    totals = run_totals(answers)

    assert totals.answers == 2
    assert totals.input_tokens == 2000
    assert totals.output_tokens == 400
    assert totals.cost.free_tier_usd == 0.0
    assert totals.cost.list_price_usd == pytest.approx(0.0006)
    assert totals.retrieval_seconds == pytest.approx(0.75)
    assert totals.generation_seconds == pytest.approx(3.5)


def test_a_run_without_answers_totals_zero() -> None:
    assert run_totals([]) == RunTotals(
        answers=0,
        input_tokens=0,
        output_tokens=0,
        cost=Cost(free_tier_usd=0.0, list_price_usd=0.0),
        retrieval_seconds=0.0,
        generation_seconds=0.0,
    )
