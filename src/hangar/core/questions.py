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
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hangar.core.corpus import DOCUMENT_ID_PATTERN

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
