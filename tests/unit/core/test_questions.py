import datetime
from typing import Any

import pydantic
import pytest

from hangar.core.questions import Evidence, QuestionRecord

# Every record here is made up: the seed questions are written by hand.


def evidence(**changes: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "document_id": "example-handbook",
        "location": "p2",
        "quote": "An example sentence.",
        "grade": 2,
    }
    item.update(changes)

    return item


def record(**changes: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "id": "q-0001",
        "question": "Example question?",
        "type": "lookup",
        "authority": "FAA",
        "expected": "answer",
        "evidence": [evidence()],
        "reference_answer": ["Example key fact."],
        "origin": "human",
        "author": "Example Author",
        "created": "2026-11-27",
        "notes": "",
    }
    fields.update(changes)

    return fields


def test_valid_record_gives_typed_fields() -> None:
    question = QuestionRecord.model_validate(record())

    assert question.id == "q-0001"
    assert question.type == "lookup"
    assert question.created == datetime.date(2026, 11, 27)
    assert question.evidence == (
        Evidence(
            document_id="example-handbook",
            location="p2",
            quote="An example sentence.",
            grade=2,
        ),
    )
    assert question.reference_answer == ("Example key fact.",)


def test_notes_may_be_left_out() -> None:
    fields = record()
    del fields["notes"]

    assert QuestionRecord.model_validate(fields).notes == ""


@pytest.mark.parametrize(
    ("location", "passage_id"),
    [
        ("p142", "example-handbook#p142"),
        ("s571.10", "example-handbook#s571.10"),
        ("front", "example-handbook#front"),
    ],
)
def test_evidence_location_gives_the_passage_id(location: str, passage_id: str) -> None:
    item = Evidence.model_validate(evidence(location=location))

    assert item.passage_id == passage_id


@pytest.mark.parametrize(
    "changes",
    [
        {"id": "q-1"},
        {"id": "Q-0001"},
        {"question": ""},
        {"type": "trivia"},
        {"authority": "EASA"},
        {"expected": "guess"},
        {"reference_answer": []},
        {"reference_answer": [""]},
        {"origin": "generated"},
        {"author": ""},
        {"created": "yesterday"},
        {"extra": "field"},
    ],
)
def test_invalid_fields_are_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(pydantic.ValidationError):
        QuestionRecord.model_validate(record(**changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"document_id": "Example Handbook"},
        {"location": "142"},
        {"location": "page 142"},
        {"location": "p0"},
        {"quote": ""},
        {"quote": "x" * 501},
        {"grade": 0},
        {"grade": 3},
    ],
)
def test_invalid_evidence_is_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(pydantic.ValidationError):
        QuestionRecord.model_validate(record(evidence=[evidence(**changes)]))


def test_an_answerable_question_needs_evidence() -> None:
    with pytest.raises(pydantic.ValidationError, match="needs at least one evidence"):
        QuestionRecord.model_validate(record(evidence=[]))


def test_an_answerable_question_needs_a_grade_2_quote() -> None:
    with pytest.raises(pydantic.ValidationError, match="grade 2"):
        QuestionRecord.model_validate(record(evidence=[evidence(grade=1)]))


def test_an_unanswerable_question_may_have_no_evidence() -> None:
    question = QuestionRecord.model_validate(
        record(type="unanswerable", authority="none", expected="abstain", evidence=[])
    )

    assert question.evidence == ()


@pytest.mark.parametrize(
    "changes",
    [
        {"type": "unanswerable", "expected": "answer"},
        {"type": "lookup", "expected": "abstain"},
        {"type": "lookup", "authority": "none"},
    ],
)
def test_type_authority_and_expected_must_agree(changes: dict[str, Any]) -> None:
    with pytest.raises(pydantic.ValidationError):
        QuestionRecord.model_validate(record(**changes))


def test_records_cannot_be_changed() -> None:
    question = QuestionRecord.model_validate(record())

    with pytest.raises(pydantic.ValidationError):
        question.type = "table"  # type: ignore[misc]
