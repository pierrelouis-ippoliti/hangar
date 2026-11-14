"""
The PDF parser on the three FAA handbooks of C1.

These tests read the downloaded documents, so they run only locally, after
`hangar fetch`, with `uv run pytest -m corpus`.
"""

from pathlib import Path

import pytest

from hangar.core.config import NormalisationConfig
from hangar.corpus.manifest import load_snapshot
from hangar.parsing.pdf import PdfPageParser
from hangar.pipelines.settings import Settings

pytestmark = pytest.mark.corpus

ROOT = Path(__file__).resolve().parents[2]
NORMALISATION = NormalisationConfig(unicode_form="NFKC", collapse_whitespace=True)

# Page count and whether the PDF has page labels, read from each file.
HANDBOOKS = {
    "faa-h-8083-30b": (677, True),
    "faa-h-8083-31b": (1052, False),
    "faa-h-8083-32b": (500, True),
}


@pytest.mark.parametrize("document_id", HANDBOOKS)
def test_every_page_of_the_handbook_becomes_a_passage(document_id: str) -> None:
    documents = load_snapshot(ROOT / "corpus" / "manifest.yaml", "c1")
    document = next(d for d in documents if d.id == document_id)
    path = Settings().data_dir / "raw" / f"{document_id}.pdf"

    if not path.is_file():
        pytest.skip(f"{path} isn't downloaded; run hangar fetch first")

    parsed = PdfPageParser(NORMALISATION).parse(document, path)
    page_count, has_labels = HANDBOOKS[document_id]
    labels = [p.location.page_label for p in parsed.passages]

    assert parsed.source_sha256 == document.sha256
    assert len(parsed.passages) == page_count
    assert all(labels) if has_labels else not any(labels)
    assert "\ufffe" not in parsed.text
