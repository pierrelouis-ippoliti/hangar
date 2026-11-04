from collections import Counter
from pathlib import Path

from hangar.corpus.manifest import load_snapshot
from hangar.files import read_yaml
from hangar.pipelines.config import load_pipeline_config

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "corpus" / "manifest.yaml"
C1_LIST = ROOT / "configs" / "corpus" / "c1.yaml"
V0_CONFIG = ROOT / "configs" / "pipelines" / "v0.yaml"


def test_committed_manifest_validates_as_snapshot_c1() -> None:
    documents = load_snapshot(MANIFEST, "c1")

    assert Counter(d.type for d in documents) == {
        "handbook": 3,
        "regulation": 1,
        "standard": 2,
        "advisory_circular": 12,
    }


def test_c1_list_matches_the_active_documents_of_the_manifest() -> None:
    c1 = read_yaml(C1_LIST)
    assert isinstance(c1, dict)

    assert c1["snapshot"] == "c1"
    assert ROOT / c1["manifest"] == MANIFEST
    assert c1["documents"] == [d.id for d in load_snapshot(MANIFEST, "c1")]


def test_v0_pipeline_reads_this_manifest_for_snapshot_c1() -> None:
    corpus = load_pipeline_config(V0_CONFIG).corpus

    assert corpus.snapshot == "c1"
    assert ROOT / corpus.manifest == MANIFEST
