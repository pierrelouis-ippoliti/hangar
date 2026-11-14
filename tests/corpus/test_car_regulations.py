"""
The CAR parser on the regulation XML of C1.

This test reads the downloaded file, so it runs only locally, after
`hangar fetch`, with `uv run pytest -m corpus`.
"""

from pathlib import Path

import pytest

from hangar.core.config import NormalisationConfig
from hangar.corpus.manifest import load_snapshot
from hangar.parsing.car import CarXmlParser
from hangar.pipelines.settings import Settings

pytestmark = pytest.mark.corpus

ROOT = Path(__file__).resolve().parents[2]
NORMALISATION = NormalisationConfig(unicode_form="NFKC", collapse_whitespace=True)
DOCUMENT_ID = "car-sor-96-433"

# Every section of Subparts 571 and 573 in the 2026-06-18 consolidation,
# repealed ones included. 573.16 to 573.29 are reserved.
EXPECTED_LABELS = (
    [f"571.{n:02d}" for n in range(1, 14)]
    + [f"573.{n:02d}" for n in range(1, 16)]
    + [f"573.{n:02d}" for n in range(30, 33)]
)


def test_every_section_of_subparts_571_and_573_becomes_a_passage() -> None:
    documents = load_snapshot(ROOT / "corpus" / "manifest.yaml", "c1")
    document = next(d for d in documents if d.id == DOCUMENT_ID)
    path = Settings().data_dir / "raw" / f"{DOCUMENT_ID}.xml"

    if not path.is_file():
        pytest.skip(f"{path} isn't downloaded; run hangar fetch first")

    parsed = CarXmlParser(NORMALISATION, ("571", "573")).parse(document, path)

    assert parsed.source_sha256 == document.sha256
    assert [p.id for p in parsed.passages] == [
        f"{DOCUMENT_ID}#s{label}" for label in EXPECTED_LABELS
    ]
    assert all(p.start < p.end for p in parsed.passages)
