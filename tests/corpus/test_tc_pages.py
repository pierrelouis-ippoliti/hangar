"""
The HTML parser on the Transport Canada pages of C1.

These tests read the downloaded pages, so they run only locally, after
`hangar fetch`, with `uv run pytest -m corpus`.
"""

from pathlib import Path

import pytest

from hangar.core.config import ContentSelectors, NormalisationConfig
from hangar.core.corpus import DocumentSpec
from hangar.corpus.manifest import load_snapshot
from hangar.parsing.tc_html import TcHtmlParser
from hangar.pipelines.settings import Settings

pytestmark = pytest.mark.corpus

ROOT = Path(__file__).resolve().parents[2]
NORMALISATION = NormalisationConfig(unicode_form="NFKC", collapse_whitespace=True)
SELECTORS = ContentSelectors(standard="//main", advisory_circular="//main")
PAGES = [
    document
    for document in load_snapshot(ROOT / "corpus" / "manifest.yaml", "c1")
    if document.format == "html"
]

# Standard 571's appendices are on a page that isn't in C1, and 573.16 to
# 573.29 don't exist.
STANDARD_LABELS = {
    "tc-std-571": [f"571.{n:02d}" for n in range(1, 14)],
    "tc-std-573": [f"573.{n:02d}" for n in range(1, 16)],
}


@pytest.mark.parametrize("document", PAGES, ids=lambda d: d.id)
def test_every_page_has_front_matter_then_numbered_sections(
    document: DocumentSpec,
) -> None:
    path = Settings().data_dir / "raw" / f"{document.id}.html"

    if not path.is_file():
        pytest.skip(f"{path} isn't downloaded; run hangar fetch first")

    parsed = TcHtmlParser(NORMALISATION, SELECTORS).parse(document, path)
    labels = [p.location.label for p in parsed.passages]

    assert parsed.source_sha256 == document.sha256
    assert parsed.warnings == ()
    assert labels[0] is None
    assert all(p.start < p.end for p in parsed.passages)

    if document.id in STANDARD_LABELS:
        assert labels[1:] == STANDARD_LABELS[document.id]
    else:
        assert labels[1] == "1.0"
