"""
The committed seed questions, checked as a seed set.

While writing the questions, run this test alone to see what is left:
`uv run pytest tests/unit/test_seed_questions.py`. Its failure lists every
problem, the counts of the mix included.
"""

from pathlib import Path

from hangar.core.questions import check_questions
from hangar.corpus.manifest import load_snapshot
from hangar.pipelines.config import load_pipeline_config

ROOT = Path(__file__).resolve().parents[2]
V0_CONFIG = ROOT / "configs" / "pipelines" / "v0.yaml"


def test_seed_questions_are_a_complete_valid_seed_set(seed_questions: Path) -> None:
    corpus = load_pipeline_config(V0_CONFIG).corpus
    documents = load_snapshot(ROOT / corpus.manifest, corpus.snapshot)

    problems = check_questions(
        seed_questions.read_text(encoding="utf-8"), {d.id for d in documents}
    )

    assert not problems, "\n".join(["", *problems])
