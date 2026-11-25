"""
Answering runs: the answer records of a run, then its run record.

``hangar ask`` and ``hangar seed run`` answer questions inside an
``AnsweringRun``. It records each answer as soon as it is made, and at the
end writes the run record: where the run came from, when it ran, and the
totals of its answers.
"""

from collections.abc import Callable
from datetime import UTC, datetime

from hangar.core.config import PipelineConfig, config_hash
from hangar.core.errors import HangarError
from hangar.core.provenance import CodeVersion
from hangar.core.records import AnswerRecord, ModelVersions, RunRecord, run_totals
from hangar.observability.recorder import RunRecorder


class ReleaseError(HangarError):
    """A release run that can't start, because its code is not a clean commit."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AnsweringRun:
    """
    One run of answers, from its start to its run record.
    """

    def __init__(
        self,
        run_id: str,
        config: PipelineConfig,
        recorder: RunRecorder,
        code: CodeVersion | None,
        *,
        release: bool = False,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        """
        Start the run.

        Args:
            run_id: The run's ID, shared with its log file.
            config: The pipeline configuration of the run.
            recorder: Where the answer records and the run record go.
            code: The git commit and dirty flag of the checkout, or None
                outside a git checkout.
            release: Whether the run produces release results, which must
                come from a clean commit.
            clock: Gives the current time, with its time zone.

        Raises:
            ReleaseError: If ``release`` is true and the checkout has
                changed or untracked files, or is not a git checkout.
        """
        if release:
            _require_clean_commit(code)

        self._run_id = run_id
        self._config = config
        self._recorder = recorder
        self._code = code
        self._clock = clock
        self._started_at = clock()
        self._answers: list[AnswerRecord] = []

    def record_answer(self, answer: AnswerRecord) -> None:
        """
        Record one answer, and keep it for the run's totals.

        Args:
            answer: The answer record.
        """
        self._recorder.record_answer(answer)
        self._answers.append(answer)

    def finish(self) -> RunRecord:
        """
        End the run and record its run record.

        Returns:
            The run record, with the totals of every recorded answer.
        """
        config = self._config
        record = RunRecord(
            run_id=self._run_id,
            config_hash=config_hash(config),
            code=self._code,
            snapshot=config.corpus.snapshot,
            models=ModelVersions(
                embedding_model=config.embedding.model,
                embedding_revision=config.embedding.revision,
                generation_model=config.generation.model,
            ),
            started_at=self._started_at,
            ended_at=self._clock(),
            totals=run_totals(self._answers),
        )
        self._recorder.record_run(record)

        return record


def _require_clean_commit(code: CodeVersion | None) -> None:
    if code is None:
        raise ReleaseError(
            "a release run needs a known commit, but this is not a git checkout"
        )

    if code.dirty:
        raise ReleaseError(
            "a release run needs a clean checkout, but the checkout of commit "
            f"{code.commit} has changed or untracked files; commit them first"
        )
