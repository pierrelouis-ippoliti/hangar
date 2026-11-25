from pathlib import Path

import pytest

from hangar.core.records import AnswerRecord, RunRecord
from hangar.observability.recorder import (
    FileRunRecorder,
    RunFolderExistsError,
    RunRecorder,
)
from tests.builders import answer_record, run_record


def test_each_answer_is_one_json_line_in_the_answers_file(tmp_path: Path) -> None:
    first, second = answer_record(question_id="q-0001"), answer_record(question_id=None)
    recorder = FileRunRecorder(tmp_path / "v0", "seed-run.jsonl")

    recorder.record_answer(first)
    recorder.record_answer(second)

    lines = (tmp_path / "v0" / "seed-run.jsonl").read_text().splitlines()
    assert [AnswerRecord.model_validate_json(line) for line in lines] == [first, second]


def test_the_run_record_goes_to_run_json(tmp_path: Path) -> None:
    record = run_record()
    recorder = FileRunRecorder(tmp_path / "run", "seed-run.jsonl")

    recorder.record_run(record)

    written = (tmp_path / "run" / "run.json").read_text()
    assert RunRecord.model_validate_json(written) == record
    assert written.endswith("}\n")


def test_a_recorder_refuses_a_run_folder_that_already_exists(tmp_path: Path) -> None:
    # Two runs started in the same second share an ID, so the second one
    # must not overwrite the first.
    FileRunRecorder(tmp_path / "run", "answers.jsonl").record_answer(answer_record())

    with pytest.raises(RunFolderExistsError, match=str(tmp_path / "run")):
        FileRunRecorder(tmp_path / "run", "answers.jsonl")

    assert (tmp_path / "run" / "answers.jsonl").read_text() != ""


def test_a_recorder_creates_the_parent_folders(tmp_path: Path) -> None:
    FileRunRecorder(tmp_path / "results" / "v0" / "run", "answers.jsonl")

    assert (tmp_path / "results" / "v0" / "run").is_dir()


def test_the_file_recorder_follows_the_recorder_interface(tmp_path: Path) -> None:
    recorder: RunRecorder = FileRunRecorder(tmp_path / "run", "answers.jsonl")

    recorder.record_answer(answer_record())

    assert (tmp_path / "run" / "answers.jsonl").exists()
