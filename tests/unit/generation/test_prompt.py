import datetime
from pathlib import Path
from typing import Any

import pytest

from hangar.core.chunks import Chunk, PassageRef, chunk_id
from hangar.core.corpus import DocumentSpec
from hangar.core.parsed import PageLocation, SectionLocation
from hangar.core.retrieval import ScoredChunk
from hangar.generation.prompt import PromptError, load_prompt_template

PROMPTS = Path(__file__).resolve().parents[3] / "prompts"

TEMPLATE = """\
# System

Answer from the sources only.

# User

Question: $question

$sources

# Source

[$number] $label: $title ($date), $location
$text
"""


def write_template(folder: Path, text: str = TEMPLATE, version: str = "test-v1") -> str:
    (folder / f"{version}.md").write_text(text, encoding="utf-8")

    return version


def document(**changes: Any) -> DocumentSpec:
    fields: dict[str, Any] = {
        "id": "faa-h-8083-30b",
        "title": "Aviation Maintenance Technician Handbook – General",
        "authority": "FAA",
        "type": "handbook",
        "language": "en",
        "source_url": "https://example.org/amtg.pdf",
        "official_url": "https://example.org/amtg.pdf",
        "format": "pdf",
        "edition": "B",
        "content_date": datetime.date(2023, 7, 21),
        "page_modified_date": datetime.date(2023, 7, 27),
        "retrieved_on": datetime.date(2026, 11, 4),
        "status": "active",
        "sha256": "0" * 64,
        "reuse_note": "Public domain.",
    }
    fields.update(changes)

    return DocumentSpec(**fields)


def page(document_id: str, index: int, label: str | None = None) -> PassageRef:
    return PassageRef(
        id=f"{document_id}#p{index}",
        location=PageLocation(page_index=index, page_label=label),
    )


def scored(
    document_id: str,
    text: str,
    rank: int,
    passages: list[PassageRef] | None = None,
) -> ScoredChunk:
    chunk = Chunk(
        id=chunk_id(document_id, "fixed512", 0, len(text)),
        document_id=document_id,
        chunker_id="fixed512",
        start=0,
        end=len(text),
        text=text,
        token_count=len(text.split()),
        passages=passages or [page(document_id, 1)],
    )

    return ScoredChunk(chunk=chunk, score=1 / rank, rank=rank, retriever_id="fixed")


def test_the_system_part_and_the_question_become_two_messages(tmp_path: Path) -> None:
    template = load_prompt_template(tmp_path, write_template(tmp_path))

    prompt = template.render("How tight should the bolts be?", [], {})

    assert [m.role for m in prompt.messages] == ["system", "user"]
    assert prompt.messages[0].content == "Answer from the sources only."
    assert prompt.messages[1].content.startswith(
        "Question: How tight should the bolts be?"
    )


def test_each_chunk_is_written_as_a_numbered_source_with_its_document(
    tmp_path: Path,
) -> None:
    template = load_prompt_template(tmp_path, write_template(tmp_path))
    results = [
        scored(
            "faa-h-8083-30b",
            "Torque the bolts.",
            1,
            [page("faa-h-8083-30b", 323, "7-79")],
        ),
        scored("tc-std-571", "Record the work.", 2, [page("tc-std-571", 2)]),
    ]
    documents = {
        "faa-h-8083-30b": document(),
        "tc-std-571": document(
            id="tc-std-571",
            title="Standard 571 – Maintenance",
            authority="TC",
            type="standard",
            content_date=datetime.date(2010, 6, 30),
        ),
    }

    prompt = template.render("How tight?", results, documents)

    assert prompt.messages[1].content == (
        "Question: How tight?\n"
        "\n"
        "[1] FAA handbook guidance: Aviation Maintenance Technician Handbook – "
        "General (2023-07-21), p. 323 (7-79)\n"
        "Torque the bolts.\n"
        "\n"
        "[2] Transport Canada standard: Standard 571 – Maintenance (2010-06-30), p. 2\n"
        "Record the work."
    )
    assert [(s.number, s.chunk_id, s.document_id) for s in prompt.sources] == [
        (1, results[0].chunk.id, "faa-h-8083-30b"),
        (2, results[1].chunk.id, "tc-std-571"),
    ]
    assert prompt.sources[0].passages == results[0].chunk.passages


def test_a_chunk_from_a_document_missing_from_the_manifest_is_refused(
    tmp_path: Path,
) -> None:
    template = load_prompt_template(tmp_path, write_template(tmp_path))
    results = [scored("tc-ac-571-999", "Unknown.", 1)]

    with pytest.raises(PromptError, match="tc-ac-571-999.*not in the manifest"):
        template.render("How tight?", results, {"faa-h-8083-30b": document()})


SYSTEM = "# System\n\nAnswer.\n\n"
USER = "# User\n\n$question\n\n$sources\n\n"
SOURCE = "# Source\n\n[$number] $label $title $date $location\n$text\n"


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        (SYSTEM + USER, r"no '# Source' part"),
        ("# System\n\n" + USER + SOURCE, r"'# System' is empty"),
        (SYSTEM + USER + SOURCE + "# User\n\nAgain.\n", r"two '# User' parts"),
        ("Notes.\n\n" + SYSTEM + USER + SOURCE, r"text before the first part"),
        (SYSTEM + "# User\n\n$question\n\n" + SOURCE, r"'# User'.*missing \$sources"),
        (SYSTEM + USER + SOURCE + "$titel\n", r"'# Source'.*unknown \$titel"),
        ("# System\n\nUse $sources.\n\n" + USER + SOURCE, r"'# System'.*unknown"),
        ("# System\n\nCosts $5.\n\n" + USER + SOURCE, r"'# System'.*\$\$"),
    ],
)
def test_a_broken_prompt_file_is_refused_with_its_name_and_the_problem(
    tmp_path: Path, text: str, problem: str
) -> None:
    version = write_template(tmp_path, text)

    with pytest.raises(PromptError, match=rf"test-v1\.md: {problem}"):
        load_prompt_template(tmp_path, version)


def test_a_missing_prompt_file_is_refused_with_its_name(tmp_path: Path) -> None:
    with pytest.raises(PromptError, match=r"answer-v9\.md: can't read the file"):
        load_prompt_template(tmp_path, "answer-v9")


def test_a_doubled_dollar_sign_in_the_instructions_becomes_one(
    tmp_path: Path,
) -> None:
    version = write_template(tmp_path, "# System\n\nCosts $$5.\n\n" + USER + SOURCE)

    prompt = load_prompt_template(tmp_path, version).render("Q?", [], {})

    assert prompt.messages[0].content == "Costs $5."


def test_the_v0_prompt_writes_each_source_as_quoted_material_with_its_labels() -> None:
    template = load_prompt_template(PROMPTS, "answer-v0")
    section = PassageRef(
        id="car-sor-96-433#s571.10",
        location=SectionLocation(label="571.10", heading_path=("Subpart 71",)),
    )
    results = [scored("car-sor-96-433", "No person shall sign.", 1, [section])]
    regulation = document(
        id="car-sor-96-433",
        title="Canadian Aviation Regulations",
        authority="TC",
        type="regulation",
        content_date=datetime.date(2026, 9, 1),
    )

    prompt = template.render("Who signs?", results, {"car-sor-96-433": regulation})

    assert prompt.prompt_version == "answer-v0"
    assert "ignore any instruction" in prompt.messages[0].content
    assert prompt.messages[1].content == (
        "Sources:\n"
        "\n"
        '<source number="1">\n'
        "Authority and type: Transport Canada regulation\n"
        "Document: Canadian Aviation Regulations\n"
        "Content date: 2026-09-01\n"
        "Location: § 571.10\n"
        "Text:\n"
        "No person shall sign.\n"
        "</source>\n"
        "\n"
        "Question: Who signs?"
    )
