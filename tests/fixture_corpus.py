"""
The fixture corpus: the test documents, a manifest with their real hashes,
and a pipeline configuration that reads it.

The documents are the FAA excerpt, the synthetic CAR XML and the synthetic
Transport Canada advisory circular in ``tests/fixtures``. The hashes are
computed when a test runs, so the fetch stage accepts the files.
"""

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from hangar.core.config import PipelineConfig
from hangar.corpus.download import LocalCopyDownloader
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.settings import Settings, load_settings

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
V0_CONFIG = ROOT / "configs" / "pipelines" / "v0.yaml"


@dataclass(frozen=True)
class FixtureDocument:
    """
    One document of the fixture corpus.

    Attributes:
        id: The document ID, such as ``example-handbook``.
        fixture: The fixture file the document is read from.
        format: The file format: ``pdf``, ``xml`` or ``html``.
        type: The document type, such as ``handbook``.
    """

    id: str
    fixture: Path
    format: str
    type: str

    @property
    def url(self) -> str:
        """
        The made-up URL the manifest gives for the document.
        """
        return f"https://example.org/{self.id}.{self.format}"

    def manifest_entry(self) -> dict[str, Any]:
        """
        The document's manifest entry, with the real hash of its fixture.
        """
        return {
            "id": self.id,
            "title": "Example",
            "authority": "FAA" if self.format == "pdf" else "TC",
            "type": self.type,
            "language": "en",
            "source_url": self.url,
            "official_url": self.url,
            "format": self.format,
            "edition": "1",
            "content_date": "2024-01-01",
            "page_modified_date": "2024-01-01",
            "retrieved_on": "2026-11-04",
            "status": "active",
            "sha256": hashlib.sha256(self.fixture.read_bytes()).hexdigest(),
            "reuse_note": "Made up for tests.",
        }


DOCUMENTS = (
    FixtureDocument(
        "example-handbook",
        FIXTURES / "pdf" / "faa-h-8083-30b-p34-36.pdf",
        "pdf",
        "handbook",
    ),
    FixtureDocument(
        "example-regulation",
        FIXTURES / "car" / "car-example.xml",
        "xml",
        "regulation",
    ),
    FixtureDocument(
        "example-ac",
        FIXTURES / "tc_html" / "tc-ac-example.html",
        "html",
        "advisory_circular",
    ),
)


@dataclass
class FixtureCorpus:
    """
    The fixture corpus, written into a test's temporary folder.

    Attributes:
        folder: The temporary folder. The data folder is its ``data``
            subfolder.
        manifest: The manifest file, marked with snapshot ``c1``.
        documents: The documents, in manifest order.
        downloader: A downloader that serves each document's fixture file
            at its manifest URL.
    """

    folder: Path
    manifest: Path
    documents: tuple[FixtureDocument, ...]
    downloader: LocalCopyDownloader

    @property
    def data_dir(self) -> Path:
        """
        The data folder, which ``HANGAR_DATA_DIR`` points at.
        """
        return self.folder / "data"

    def settings(self) -> Settings:
        """
        The environment settings, read without a ``.env`` file.
        """
        return load_settings(None)

    def write_config(self, **checks: Any) -> Path:
        """
        Write the v0 pipeline configuration, changed to read the fixture
        manifest.

        Args:
            **checks: Parse thresholds that replace the defaults, such as
                ``min_characters=1500``.

        Returns:
            The configuration file.
        """
        data = yaml.safe_load(V0_CONFIG.read_text())
        data["corpus"]["manifest"] = str(self.manifest)
        # The fixtures are much shorter than real documents.
        data["parsing"]["checks"]["min_characters"] = 100
        data["parsing"]["checks"].update(checks)

        path = self.folder / "pipeline.yaml"
        path.write_text(yaml.safe_dump(data))

        return path

    def config(self, **checks: Any) -> PipelineConfig:
        """
        Write the pipeline configuration and load it.

        Args:
            **checks: Parse thresholds that replace the defaults.

        Returns:
            The validated configuration.
        """
        return load_pipeline_config(self.write_config(**checks))

    def copy_raw(self) -> None:
        """
        Copy each document into the raw folder, as the fetch stage would.
        """
        raw = self.data_dir / "raw"
        raw.mkdir(parents=True, exist_ok=True)

        for document in self.documents:
            shutil.copy(document.fixture, raw / f"{document.id}.{document.format}")


def write_fixture_corpus(folder: Path) -> FixtureCorpus:
    """
    Write the fixture manifest into a folder.

    Args:
        folder: The folder, usually a test's temporary folder.

    Returns:
        The fixture corpus, with a fresh downloader.
    """
    manifest = folder / "manifest.yaml"
    entries = [document.manifest_entry() for document in DOCUMENTS]
    manifest.write_text(yaml.safe_dump({"snapshot": "c1", "documents": entries}))
    downloader = LocalCopyDownloader({d.url: d.fixture for d in DOCUMENTS})

    return FixtureCorpus(folder, manifest, DOCUMENTS, downloader)
