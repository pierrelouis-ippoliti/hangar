"""
The committed seed questions, checked as a seed set.

While writing the questions, run this test alone to see what is left:
`uv run pytest tests/unit/test_seed_questions.py`. Its failure lists every
problem, the counts of the mix included.
"""

from pathlib import Path

import pytest

from hangar.core.questions import check_questions
from hangar.corpus.manifest import load_snapshot
from hangar.pipelines.config import load_pipeline_config

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "eval" / "seed" / "questions.jsonl"
V0_CONFIG = ROOT / "configs" / "pipelines" / "v0.yaml"


def test_seed_questions_are_a_complete_valid_seed_set() -> None:
    if not QUESTIONS.is_file():
        pytest.skip(
            "eval/seed/questions.jsonl doesn't exist yet; the maintainer writes "
            "it by hand (#30)"
        )

    corpus = load_pipeline_config(V0_CONFIG).corpus
    documents = load_snapshot(ROOT / corpus.manifest, corpus.snapshot)

    problems = check_questions(
        QUESTIONS.read_text(encoding="utf-8"), {d.id for d in documents}
    )

    assert not problems, "\n".join(["", *problems])
