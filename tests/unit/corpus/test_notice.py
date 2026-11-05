from pathlib import Path

import pytest

from hangar.core.corpus import parse_manifest
from hangar.files import read_yaml

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "corpus" / "manifest.yaml"
NOTICE = ROOT / "NOTICE.md"

DOCUMENTS = parse_manifest(read_yaml(MANIFEST), str(MANIFEST)).documents


@pytest.mark.parametrize("document_id", [d.id for d in DOCUMENTS])
def test_notice_covers_every_document_of_the_manifest(document_id: str) -> None:
    # Cancelled documents are included: the manifest keeps them on record.
    assert f"`{document_id}`" in NOTICE.read_text(encoding="utf-8")
