"""
Seed question records: the questions Hangar is measured on, written by hand.

Each record holds a question, what Hangar should do with it, the evidence
that answers it and the reference answer as key facts. The format is the one
the v1 evaluation reads, so the v0 seed set is never rewritten.

Evidence points to a passage by its location and holds a quote from it.
Offsets belong to one parse, but a quote survives a change of parser, so
evidence is matched by quote.
"""

import datetime
import json
import re
from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from hangar.core.corpus import DOCUMENT_ID_PATTERN
from hangar.core.errors import field_problems

QUESTION_ID_PATTERN = r"^q-[0-9]{4}$"

# The part of a passage ID after the ``#``: ``p142`` for a PDF page index,
# ``s571.10`` for a section label, ``front`` for the front matter.
LOCATION_PATTERN = r"^(p[1-9][0-9]*|s[0-9A-Za-z][0-9A-Za-z.\-]*|front)$"

# A quote is one or two sentences. The records are committed, and the
# documents are never redistributed (ADR-0003), so a quote stays short.
MAX_QUOTE_CHARACTERS = 500

QuestionType = Literal[
    "lookup",
    "table",
    "procedure",
    "explanation",
    "regulatory",
    "identifier",
    "multi-part",
    "unanswerable",
]
QuestionAuthority = Literal["FAA", "TC", "both", "none"]
# ``ask_authority``: Hangar should ask whether the FAA or Transport Canada
# applies.
ExpectedBehaviour = Literal["answer", "abstain", "ask_authority"]

# The target mix of the seed set (#30): 50 questions in all.
TYPE_TARGETS: dict[QuestionType, int] = {
    "lookup": 8,
    "table": 8,
    "procedure": 7,
    "explanation": 5,
    "regulatory": 8,
    "identifier": 5,
    "multi-part": 4,
    "unanswerable": 5,
}
SEED_SET_SIZE = sum(TYPE_TARGETS.values())
# "About 30 on FAA material and 15 on Transport Canada material": a count
# within this many questions of its target is on target.
AUTHORITY_TARGETS: dict[QuestionAuthority, int] = {"FAA": 30, "TC": 15}
AUTHORITY_TOLERANCE = 3


class QuestionModel(BaseModel):
    """
    A part of a question record: frozen, and with no unknown fields.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class Evidence(QuestionModel):
    """
    A passage that answers a question, or helps to, with a quote from it.

    Attributes:
        document_id: The manifest ID of the document, such as
            ``faa-h-8083-31b``.
        location: The passage within the document, written as the end of
            its passage ID: ``p142`` for the PDF page at index 142 (its
            position in the file, not its printed label), ``s571.10`` for a
            section, ``front`` for the front matter.
        quote: One or two sentences copied word for word from the parsed
            text of the passage. Only whitespace may differ.
        grade: 2 when the quote answers the question, 1 when it helps.
    """

    document_id: str = Field(pattern=DOCUMENT_ID_PATTERN)
    location: str = Field(pattern=LOCATION_PATTERN)
    quote: str = Field(min_length=1, max_length=MAX_QUOTE_CHARACTERS)
    grade: Literal[1, 2]

    @property
    def passage_id(self) -> str:
        """
        The ID of the passage the evidence points to, such as ``doc#p142``
        """
        return f"{self.document_id}#{self.location}"


class QuestionRecord(QuestionModel):
    """
    One seed question, as a line of ``eval/seed/questions.jsonl``.

    Attributes:
        id: ``q-0001`` to ``q-0050``.
        question: The question as a technician or student would ask it.
        type: The kind of question, such as ``lookup`` or ``unanswerable``.
        authority: Whose material answers it: ``FAA``, ``TC``, ``both``, or
            ``none`` for an unanswerable question.
        expected: What Hangar should do: ``answer``, ``abstain``, or
            ``ask_authority`` to ask which authority applies. Only an
            unanswerable question expects ``abstain``.
        evidence: The passages that answer the question. Every question that
            doesn't expect ``abstain`` has at least one, with grade 2.
        reference_answer: The answer, split into key facts.
        origin: Who wrote the question: ``human`` for every v0 question.
        author: The person who wrote it.
        created: The day it was written.
        notes: Remarks, such as why a question is unanswerable.
    """

    id: str = Field(pattern=QUESTION_ID_PATTERN)
    question: str = Field(min_length=1)
    type: QuestionType
    authority: QuestionAuthority
    expected: ExpectedBehaviour
    evidence: tuple[Evidence, ...]
    reference_answer: tuple[str, ...] = Field(min_length=1)
    origin: Literal["human"]
    author: str = Field(min_length=1)
    created: datetime.date
    notes: str = ""

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        self._check_type_agrees()
        self._check_evidence()

        if any(not fact.strip() for fact in self.reference_answer):
            raise ValueError("every key fact of the reference answer needs text")

        return self

    def _check_type_agrees(self) -> None:
        unanswerable = self.type == "unanswerable"

        if unanswerable != (self.expected == "abstain"):
            raise ValueError(
                "an unanswerable question expects abstain, and only an "
                "unanswerable question does"
            )

        if self.authority == "none" and not unanswerable:
            raise ValueError("only an unanswerable question has authority none")

    def _check_evidence(self) -> None:
        if self.expected == "abstain":
            return

        if not self.evidence:
            raise ValueError(
                f"a question that expects {self.expected} needs at least one "
                "evidence item"
            )

        if all(item.grade != 2 for item in self.evidence):
            raise ValueError(
                "at least one evidence item needs grade 2, a quote that "
                "answers the question"
            )


@dataclass(frozen=True)
class _Reading:
    """
    What reading a questions file found, with line numbers for the problems.

    Attributes:
        ids: The line number and ID of every line that holds an ID, valid
            or not.
        records: The line number and record of every valid line.
        problems: The problems of the lines that aren't valid.
    """

    ids: list[tuple[int, str]]
    records: list[tuple[int, QuestionRecord]]
    problems: list[str]


def read_questions(text: str) -> tuple[list[QuestionRecord], list[str]]:
    """
    Read the lines of a questions file, keeping every valid record.

    Each non-blank line is one JSON record. A line that isn't valid gives
    one problem per failed check instead of stopping the reading.

    Args:
        text: The content of the file, such as ``eval/seed/questions.jsonl``.

    Returns:
        The valid records in file order, and the problems of the other
        lines. Each problem starts with the question ID and line number,
        such as ``q-0003 (line 3): evidence[0].grade: ...``, or with only the
        line number when the line has no ID.
    """
    reading = _read(text)

    return [record for _, record in reading.records], reading.problems


def check_questions(text: str, document_ids: Collection[str]) -> list[str]:
    """
    Check a questions file as a seed set, listing every problem found.

    On top of each record's own checks, the IDs must be unique and run from
    ``q-0001`` with no gap, evidence must point to documents of the
    snapshot, and the set must follow the target mix. The mix problems give
    the counts, so they show the progress of a set still being written.

    Args:
        text: The content of the file, such as ``eval/seed/questions.jsonl``.
        document_ids: The IDs of the documents in the snapshot.

    Returns:
        Every problem, in plain words, each naming its question when it has
        one; mix problems start with ``mix:``. An empty list means the set
        is ready.
    """
    reading = _read(text)
    records = [record for _, record in reading.records]

    return [
        *reading.problems,
        *_id_problems(reading.ids),
        *_document_problems(reading.records, document_ids),
        *_mix_problems(records),
    ]


def _read(text: str) -> _Reading:
    reading = _Reading(ids=[], records=[], problems=[])

    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue

        try:
            data = json.loads(line)
        except json.JSONDecodeError as error:
            reading.problems.append(f"line {number}: not valid JSON ({error.msg})")
            continue

        question_id = data.get("id") if isinstance(data, dict) else None

        if isinstance(question_id, str) and question_id:
            reading.ids.append((number, question_id))
            name = f"{question_id} (line {number})"
        else:
            name = f"line {number}"

        try:
            reading.records.append((number, QuestionRecord.model_validate(data)))
        except ValidationError as error:
            reading.problems.extend(
                f"{name}: {p.field}: {p.message}" if p.field else f"{name}: {p.message}"
                for p in field_problems(error)
            )

    return reading


def _id_problems(ids: Sequence[tuple[int, str]]) -> list[str]:
    problems = []
    first_line: dict[str, int] = {}

    for number, question_id in ids:
        if question_id in first_line:
            problems.append(
                f"{question_id} (line {number}): the ID is already used "
                f"on line {first_line[question_id]}"
            )
        else:
            first_line[question_id] = number

    numbers = {
        int(question_id.removeprefix("q-"))
        for question_id in first_line
        if re.fullmatch(QUESTION_ID_PATTERN, question_id)
    }

    if numbers:
        last = max(numbers)
        problems.extend(
            f"q-{n:04d}: missing; the IDs run from q-0001 to q-{last:04d}"
            for n in range(1, last + 1)
            if n not in numbers
        )

    return problems


def _document_problems(
    records: Sequence[tuple[int, QuestionRecord]], document_ids: Collection[str]
) -> list[str]:
    return [
        f"{record.id} (line {number}): evidence[{position}].document_id: "
        f"{item.document_id} is not a document of the snapshot"
        for number, record in records
        for position, item in enumerate(record.evidence)
        if item.document_id not in document_ids
    ]


def _mix_problems(records: Sequence[QuestionRecord]) -> list[str]:
    problems = []

    if len(records) != SEED_SET_SIZE:
        problems.append(f"mix: {len(records)} questions, the target is {SEED_SET_SIZE}")

    types = Counter(record.type for record in records)
    problems.extend(
        f"mix: {types[kind]} {kind} questions, the target is {target}"
        for kind, target in TYPE_TARGETS.items()
        if types[kind] != target
    )

    authorities = Counter(record.authority for record in records)

    for authority, target in AUTHORITY_TARGETS.items():
        low, high = target - AUTHORITY_TOLERANCE, target + AUTHORITY_TOLERANCE

        if not low <= authorities[authority] <= high:
            problems.append(
                f"mix: {authorities[authority]} {authority} questions, "
                f"the target is about {target} ({low} to {high})"
            )

    return problems
