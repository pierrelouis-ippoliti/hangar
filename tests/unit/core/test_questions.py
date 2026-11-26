import datetime
import json
from typing import Any

import pydantic
import pytest

from hangar.core.questions import (
    Evidence,
    QuestionRecord,
    check_questions,
    quote_appears,
    read_questions,
)

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


# The validator reads the whole file and lists every problem.

DOCUMENT_IDS = {"example-handbook", "example-ac"}


def jsonl(*records: dict[str, Any]) -> str:
    return "\n".join(json.dumps(r) for r in records) + "\n"


def numbered(count: int, **changes: Any) -> list[dict[str, Any]]:
    return [record(id=f"q-{n:04d}", **changes) for n in range(1, count + 1)]


def full_mix() -> list[dict[str, Any]]:
    kinds = (
        [("lookup", "FAA")] * 8
        + [("table", "FAA")] * 8
        + [("procedure", "FAA")] * 7
        + [("explanation", "FAA")] * 5
        + [("regulatory", "TC")] * 8
        + [("identifier", "TC")] * 5
        + [("multi-part", "FAA")] * 2
        + [("multi-part", "TC")] * 2
        + [("unanswerable", "none")] * 5
    )
    records = []

    for n, (kind, authority) in enumerate(kinds, start=1):
        changes: dict[str, Any] = {"type": kind, "authority": authority}

        if kind == "unanswerable":
            changes.update(expected="abstain", evidence=[])

        records.append(record(id=f"q-{n:04d}", **changes))

    return records


def mix_problems(problems: list[str]) -> list[str]:
    return [p for p in problems if p.startswith("mix: ")]


def test_read_questions_gives_the_valid_records() -> None:
    questions, problems = read_questions(jsonl(*numbered(2)))

    assert [q.id for q in questions] == ["q-0001", "q-0002"]
    assert problems == []


def test_read_questions_skips_blank_lines() -> None:
    questions, problems = read_questions("\n" + jsonl(record()) + "\n\n")

    assert len(questions) == 1
    assert problems == []


def test_read_questions_names_the_question_and_field_of_each_problem() -> None:
    text = jsonl(
        record(id="q-0001", type="trivia"),
        record(id="q-0002"),
        record(id="q-0003", evidence=[evidence(grade=5)]),
    )

    questions, problems = read_questions(text)

    assert [q.id for q in questions] == ["q-0002"]
    assert len(problems) == 2
    assert problems[0].startswith("q-0001 (line 1): type: ")
    assert problems[1].startswith("q-0003 (line 3): evidence[0].grade: ")


def test_read_questions_names_the_line_when_there_is_no_id() -> None:
    fields = record()
    del fields["id"]

    _, problems = read_questions("{not json\n" + jsonl(fields) + "[1, 2]\n")

    assert problems[0].startswith("line 1: not valid JSON")
    assert problems[1] == "line 2: id: Field required"
    assert problems[2].startswith("line 3: ")


def test_a_full_valid_set_has_no_problems() -> None:
    assert check_questions(jsonl(*full_mix()), DOCUMENT_IDS) == []


def test_duplicate_and_missing_ids_are_reported() -> None:
    records = numbered(4)
    records[2]["id"] = "q-0002"

    problems = check_questions(jsonl(*records), DOCUMENT_IDS)

    assert "q-0002 (line 3): the ID is already used on line 2" in problems
    assert "q-0003: missing; the IDs run from q-0001 to q-0004" in problems


def test_document_ids_outside_the_snapshot_are_reported() -> None:
    records = numbered(1, evidence=[evidence(), evidence(document_id="other-doc")])

    problems = check_questions(jsonl(*records), DOCUMENT_IDS)

    assert (
        "q-0001 (line 1): evidence[1].document_id: other-doc is not a document "
        "of the snapshot" in problems
    )


def test_the_mix_reports_the_count_of_each_type_off_target() -> None:
    problems = check_questions(jsonl(*numbered(3)), DOCUMENT_IDS)

    assert mix_problems(problems) == [
        "mix: 3 questions, the target is 50",
        "mix: 3 lookup questions, the target is 8",
        "mix: 0 table questions, the target is 8",
        "mix: 0 procedure questions, the target is 7",
        "mix: 0 explanation questions, the target is 5",
        "mix: 0 regulatory questions, the target is 8",
        "mix: 0 identifier questions, the target is 5",
        "mix: 0 multi-part questions, the target is 4",
        "mix: 0 unanswerable questions, the target is 5",
        "mix: 3 FAA questions, the target is about 30 (27 to 33)",
        "mix: 0 TC questions, the target is about 15 (12 to 18)",
    ]


def test_the_authority_mix_allows_a_few_questions_either_way() -> None:
    records = full_mix()

    # 28 FAA and 14 TC: three questions moved to both.
    for position in (0, 1, 30):
        records[position]["authority"] = "both"

    assert check_questions(jsonl(*records), DOCUMENT_IDS) == []


def test_every_problem_is_reported_at_once() -> None:
    records = full_mix()
    records[0]["question"] = ""
    records[1]["evidence"] = [evidence(document_id="other-doc")]

    problems = check_questions(jsonl(*records), DOCUMENT_IDS)

    assert problems[0].startswith("q-0001 (line 1): question: ")
    assert problems[1].startswith("q-0002 (line 2): evidence[0].document_id: ")
    assert mix_problems(problems) == [
        "mix: 49 questions, the target is 50",
        "mix: 7 lookup questions, the target is 8",
    ]


# A quote matches its passage word for word; only whitespace may differ.


@pytest.mark.parametrize(
    "quote",
    [
        "Torque the bolt.",
        "the bolt. Then",
        "Torque the  bolt.",
        "Torque the bolt.\nThen check",
        "  Torque the bolt.  ",
    ],
)
def test_quote_found_in_the_passage_whatever_its_whitespace(quote: str) -> None:
    passage = "Step 1:\nTorque the \nbolt. Then\tcheck it."

    assert quote_appears(quote, passage)


@pytest.mark.parametrize(
    "quote",
    [
        "torque the bolt.",
        "Torquethe bolt.",
        "Torque the bolt, then check",
        "Torque the bolt. Then check it’s",
        "",
        "   ",
    ],
)
def test_quote_with_any_other_difference_is_not_found(quote: str) -> None:
    passage = "Step 1:\nTorque the \nbolt. Then check it's done."

    assert not quote_appears(quote, passage)
