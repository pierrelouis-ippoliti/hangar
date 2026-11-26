"""
Each evidence quote of the seed questions, found in the parsed documents.

A quote must appear word for word in the parsed text of the passage at its
location; only whitespace may differ (see ``core.questions.quote_appears``).
This test reads `data/parsed`, so it runs only locally, after `hangar parse`:
`uv run pytest -m corpus tests/corpus/test_seed_quotes.py`.
"""

from pathlib import Path

import pytest

from hangar.core.config import PipelineConfig
from hangar.core.parsed import ParsedDocument
from hangar.core.questions import Evidence, quote_appears, read_questions
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.passage import PassageError, load_parsed_document
from hangar.pipelines.settings import Settings

pytestmark = pytest.mark.corpus

ROOT = Path(__file__).resolve().parents[2]
V0_CONFIG = ROOT / "configs" / "pipelines" / "v0.yaml"


def test_every_evidence_quote_appears_in_its_passage(seed_questions: Path) -> None:
    settings, config = Settings(), load_pipeline_config(V0_CONFIG)
    parsed_dir = settings.data_dir / "parsed" / config.corpus.snapshot

    if not parsed_dir.is_dir():
        pytest.skip(f"{parsed_dir} doesn't exist; run hangar parse first")

    # Invalid records are left to tests/unit/test_seed_questions.py.
    questions, _ = read_questions(seed_questions.read_text(encoding="utf-8"))
    documents: dict[str, ParsedDocument | PassageError] = {}
    problems = []

    for question in questions:
        for position, item in enumerate(question.evidence):
            problem = quote_problem(item, documents, settings, config)

            if problem:
                problems.append(f"{question.id}: evidence[{position}]: {problem}")

    assert not problems, "\n".join(["", *problems])


def quote_problem(
    item: Evidence,
    documents: dict[str, ParsedDocument | PassageError],
    settings: Settings,
    config: PipelineConfig,
) -> str | None:
    """What is wrong with an evidence item's quote, or None if it is found."""
    if item.document_id not in documents:
        try:
            documents[item.document_id] = load_parsed_document(
                settings, config, item.document_id
            )
        except PassageError as error:
            documents[item.document_id] = error

    document = documents[item.document_id]

    if isinstance(document, PassageError):
        return str(document)

    passage = document.passage(item.passage_id)

    if passage is None:
        return f"{item.passage_id} is not a passage of the parsed document"

    if not quote_appears(item.quote, document.passage_text(passage)):
        return f"the quote isn't in {item.passage_id}, word for word"

    return None
