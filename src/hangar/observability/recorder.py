"""
Run recorders: where the answer records and the run record of a run go.

v0 writes them to files under ``results/``: one JSON line per answer, then
``run.json``. Tests point the same recorder at a temporary folder. v1 adds
a recorder that sends them to Weights & Biases.
"""

from pathlib import Path
from typing import Protocol

from hangar.core.records import AnswerRecord, RunRecord

RUN_FILE = "run.json"


class RunRecorder(Protocol):
    """
    Keeps the records of one answering run.
    """

    def record_answer(self, answer: AnswerRecord) -> None:
        """
        Keep the record of one answer, as soon as it is made.

        Args:
            answer: The answer record.
        """
        ...

    def record_run(self, run: RunRecord) -> None:
        """
        Keep the run record, once every answer is recorded.

        Args:
            run: The run record.
        """
        ...


class FileRunRecorder:
    """
    Writes a run's answer records to a JSON lines file, and its run record.

    Both files sit in one folder, such as ``results/v0``, the run record in
    ``run.json``. Each answer is appended as soon as it is recorded, so a
    run that stops halfway keeps the answers it already has.
    """

    def __init__(self, folder: Path, answers_file: str) -> None:
        """
        Set up the recorder, and empty the answers file of an earlier run.

        Args:
            folder: The folder of both files. It is created if needed.
            answers_file: The name of the answers file, such as
                ``seed-run.jsonl``.
        """
        folder.mkdir(parents=True, exist_ok=True)
        self.answers_path = folder / answers_file
        self.run_path = folder / RUN_FILE

        # The files hold one run, so the answers of an earlier run go.
        self.answers_path.write_text("", encoding="utf-8")

    def record_answer(self, answer: AnswerRecord) -> None:
        """
        Append an answer record to the answers file, as one JSON line.

        Args:
            answer: The answer record.
        """
        with self.answers_path.open("a", encoding="utf-8") as answers:
            answers.write(answer.model_dump_json() + "\n")

    def record_run(self, run: RunRecord) -> None:
        """
        Write the run record to ``run.json``, replacing an earlier one.

        Args:
            run: The run record.
        """
        self.run_path.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
