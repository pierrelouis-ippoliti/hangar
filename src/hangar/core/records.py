"""
Run and answer records: what a run did, kept to explain any answer later.

The language model's output can vary even at temperature 0, so every
answer is stored rather than assumed reproducible. An answering run writes
one answer record per question, then one run record with where the run
came from and its totals. Both are written by a run recorder.
"""

from collections.abc import Sequence
from typing import Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    model_validator,
)

from hangar.core.chunks import CHUNK_ID_LENGTH, PassageRef, Sha256
from hangar.core.citations import Citation
from hangar.core.completions import Completion
from hangar.core.config import CommitHash
from hangar.core.corpus import DOCUMENT_ID_PATTERN
from hangar.core.costs import Cost, total_cost
from hangar.core.provenance import CodeVersion
from hangar.core.retrieval import ScoredChunk


class RecordModel(BaseModel):
    """
    A part of a run or answer record: frozen, and with no unknown fields.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class StageTimings(RecordModel):
    """
    How long each step of answering one question took, in seconds.

    Attributes:
        retrieval_seconds: Finding the chunks, embedding the question
            included.
        generation_seconds: Getting the completion, waits for the rate
            limit and retries included.
    """

    retrieval_seconds: NonNegativeFloat
    generation_seconds: NonNegativeFloat


class ScoredChunkRef(RecordModel):
    """
    A retrieved chunk as an answer record keeps it: where it is, not its text.

    Answer records are committed, and the documents are never redistributed
    (ADR-0003), so the record keeps enough to find the chunk again in the
    chunks file, and no more.

    Attributes:
        chunk_id: The chunk's ID.
        score: How well it matched the question, as the retriever measured
            it. Higher is better.
        document_id: The manifest ID of the chunk's document.
        passages: The pages or sections the chunk covers, in text order.
    """

    chunk_id: str = Field(pattern=rf"^[0-9a-f]{{{CHUNK_ID_LENGTH}}}$")
    score: float
    document_id: str = Field(pattern=DOCUMENT_ID_PATTERN)
    passages: tuple[PassageRef, ...] = Field(min_length=1)

    @classmethod
    def of(cls, scored: ScoredChunk) -> Self:
        """
        Make the reference of a retrieval result.

        Args:
            scored: The retrieved chunk, with its score.

        Returns:
            The reference, without the chunk's text.
        """
        return cls(
            chunk_id=scored.chunk.id,
            score=scored.score,
            document_id=scored.chunk.document_id,
            passages=scored.chunk.passages,
        )


class AnswerRecord(RecordModel):
    """
    Everything about one answer: the question, what was found, what was written.

    Attributes:
        run_id: The run that produced it.
        question_id: The seed question's ID, such as ``q-0001``, or None
            for a question asked with ``hangar ask``.
        question: The question as asked.
        scored_chunks: The retrieved chunks, best first, without their
            text.
        prompt_version: The prompt file used, such as ``answer-v0``.
        completion: The language model's completion, with its token
            counts.
        citations: The citations parsed from the answer, invalid ones
            included.
        timings: How long retrieval and generation took.
        cost: What the completion's tokens cost.
    """

    run_id: str = Field(min_length=1)
    question_id: str | None
    question: str = Field(min_length=1)
    scored_chunks: tuple[ScoredChunkRef, ...]
    prompt_version: str = Field(min_length=1)
    completion: Completion
    citations: tuple[Citation, ...]
    timings: StageTimings
    cost: Cost


class ModelVersions(RecordModel):
    """
    The models a run used, pinned.

    Attributes:
        embedding_model: The embedding model's Hugging Face ID, such as
            ``BAAI/bge-m3``.
        embedding_revision: The embedding model's commit hash.
        generation_model: The language model's dated ID, such as
            ``mistral-small-2603``.
    """

    embedding_model: str = Field(min_length=1)
    embedding_revision: CommitHash
    generation_model: str = Field(min_length=1)


class RunTotals(RecordModel):
    """
    The sums over every answer of a run.

    Attributes:
        answers: How many answers the run recorded.
        input_tokens: The prompt tokens of every completion.
        output_tokens: The answer tokens of every completion.
        cost: What all those tokens cost.
        retrieval_seconds: The time spent retrieving, in seconds.
        generation_seconds: The time spent generating, in seconds.
    """

    answers: NonNegativeInt
    input_tokens: NonNegativeInt
    output_tokens: NonNegativeInt
    cost: Cost
    retrieval_seconds: NonNegativeFloat
    generation_seconds: NonNegativeFloat


class RunRecord(RecordModel):
    """
    Where an answering run came from, when it ran, and its totals.

    Attributes:
        run_id: The run's ID, also the name of its log file.
        config_hash: The hash of the pipeline configuration.
        code: The git commit and dirty flag, or None when the run was not
            started from a git checkout.
        release: Whether it was a release run, which only starts from a
            clean commit.
        snapshot: The corpus snapshot, such as ``c1``.
        models: The embedding and language models, pinned.
        started_at: When the run started.
        ended_at: When the run ended.
        totals: The tokens, cost and time of all its answers.
    """

    run_id: str = Field(min_length=1)
    config_hash: Sha256
    code: CodeVersion | None
    release: bool
    snapshot: str = Field(min_length=1)
    models: ModelVersions
    started_at: AwareDatetime
    ended_at: AwareDatetime
    totals: RunTotals

    @model_validator(mode="after")
    def _check_end_follows_start(self) -> Self:
        if self.ended_at < self.started_at:
            raise ValueError(
                f"run {self.run_id} ends before it starts: "
                f"{self.ended_at.isoformat()} < {self.started_at.isoformat()}"
            )

        return self


def run_totals(answers: Sequence[AnswerRecord]) -> RunTotals:
    """
    Add up the tokens, costs and stage timings of a run's answers.

    Args:
        answers: The run's answer records.

    Returns:
        The totals; zero for a run without answers.
    """
    return RunTotals(
        answers=len(answers),
        input_tokens=sum(answer.completion.input_tokens for answer in answers),
        output_tokens=sum(answer.completion.output_tokens for answer in answers),
        cost=total_cost(answer.cost for answer in answers),
        retrieval_seconds=sum(answer.timings.retrieval_seconds for answer in answers),
        generation_seconds=sum(answer.timings.generation_seconds for answer in answers),
    )
