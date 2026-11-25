import json
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from hangar.core.config import config_hash
from hangar.core.provenance import CodeVersion
from hangar.core.records import AnswerRecord, run_totals
from hangar.observability.recorder import FileRunRecorder
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.runs import AnsweringRun, ReleaseError
from tests.builders import RUN_ID, STARTED_AT, answer_record

ROOT = Path(__file__).resolve().parents[3]
CONFIG = load_pipeline_config(ROOT / "configs" / "pipelines" / "v0.yaml")
CLEAN = CodeVersion(commit="0123456789" * 4, dirty=False)
DIRTY = CodeVersion(commit="0123456789" * 4, dirty=True)


def clock(*seconds: float) -> Callable[[], datetime]:
    """A clock that gives the start time plus each number of seconds in turn."""
    times = iter(STARTED_AT + timedelta(seconds=s) for s in seconds)

    return lambda: next(times)


def start(
    folder: Path, code: CodeVersion | None, *, release: bool = False
) -> AnsweringRun:
    return AnsweringRun(
        RUN_ID,
        CONFIG,
        FileRunRecorder(folder, "answers.jsonl"),
        code,
        release=release,
        clock=clock(0, 90),
    )


def test_a_release_run_on_a_dirty_tree_fails(tmp_path: Path) -> None:
    with pytest.raises(ReleaseError, match="changed or untracked files"):
        start(tmp_path, DIRTY, release=True)


def test_a_release_run_outside_a_git_checkout_fails(tmp_path: Path) -> None:
    with pytest.raises(ReleaseError, match="not a git checkout"):
        start(tmp_path, None, release=True)


def test_a_release_run_on_a_clean_tree_records_its_commit(tmp_path: Path) -> None:
    record = start(tmp_path, CLEAN, release=True).finish()

    assert record.code == CLEAN


def test_a_run_that_is_not_a_release_may_have_changes(tmp_path: Path) -> None:
    record = start(tmp_path, DIRTY).finish()

    assert record.code == DIRTY


def test_each_answer_is_recorded_as_it_comes(tmp_path: Path) -> None:
    run = start(tmp_path, CLEAN)

    run.record_answer(answer_record(question_id="q-0001"))

    (line,) = (tmp_path / "answers.jsonl").read_text().splitlines()
    assert AnswerRecord.model_validate_json(line).question_id == "q-0001"


def test_finishing_writes_the_run_record_with_its_totals(tmp_path: Path) -> None:
    answers = [answer_record(question_id="q-0001"), answer_record(question_id="q-0002")]
    run = start(tmp_path, CLEAN)

    for answer in answers:
        run.record_answer(answer)

    record = run.finish()

    assert record.run_id == RUN_ID
    assert record.config_hash == config_hash(CONFIG)
    assert record.snapshot == "c1"
    assert record.models.embedding_model == "BAAI/bge-m3"
    assert record.models.embedding_revision == CONFIG.embedding.revision
    assert record.models.generation_model == "mistral-small-2603"
    assert record.started_at == STARTED_AT
    assert record.ended_at == STARTED_AT + timedelta(seconds=90)
    assert record.totals == run_totals(answers)
    assert json.loads((tmp_path / "run.json").read_text())["run_id"] == RUN_ID
