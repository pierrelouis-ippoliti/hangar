import hashlib
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from hangar.core.config import PipelineConfig, config_hash
from hangar.core.parsed import ParsedFile
from hangar.parsing.parser import ParseError
from hangar.parsing.report import ParseCheckError, ParseReport
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.parse import run_parse
from hangar.pipelines.settings import Settings, load_settings

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures"
V0_CONFIG = ROOT / "configs" / "pipelines" / "v0.yaml"

# Each test document: its ID, fixture, format and type.
DOCUMENTS = [
    ("example-handbook", "pdf/faa-h-8083-30b-p34-36.pdf", "pdf", "handbook"),
    ("example-regulation", "car/car-example.xml", "xml", "regulation"),
    ("example-ac", "tc_html/tc-ac-example.html", "html", "advisory_circular"),
]


def entry(document_id: str, fixture: str, fmt: str, kind: str) -> dict[str, Any]:
    return {
        "id": document_id,
        "title": "Example",
        "authority": "FAA" if fmt == "pdf" else "TC",
        "type": kind,
        "language": "en",
        "source_url": f"https://example.org/{document_id}",
        "official_url": f"https://example.org/{document_id}",
        "format": fmt,
        "edition": "1",
        "content_date": "2024-01-01",
        "page_modified_date": "2024-01-01",
        "retrieved_on": "2026-11-04",
        "status": "active",
        "sha256": hashlib.sha256((FIXTURES / fixture).read_bytes()).hexdigest(),
        "reuse_note": "Made up for tests.",
    }


def setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **checks: Any
) -> tuple[Settings, PipelineConfig]:
    """Copy the fixtures into a raw folder, with a manifest and a config."""
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)

    for document_id, fixture, fmt, _ in DOCUMENTS:
        shutil.copy(FIXTURES / fixture, raw / f"{document_id}.{fmt}")

    manifest = tmp_path / "manifest.yaml"
    documents = [entry(*document) for document in DOCUMENTS]
    manifest.write_text(yaml.safe_dump({"snapshot": "c1", "documents": documents}))

    data = yaml.safe_load(V0_CONFIG.read_text())
    data["corpus"]["manifest"] = str(manifest)
    # The fixtures are much shorter than real documents.
    data["parsing"]["checks"]["min_characters"] = 100
    data["parsing"]["checks"].update(checks)
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(yaml.safe_dump(data))

    monkeypatch.setenv("HANGAR_DATA_DIR", str(tmp_path / "data"))

    return load_settings(None), load_pipeline_config(config_path)


def test_every_document_is_parsed_into_the_snapshot_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)

    run_parse(settings, config, results_dir=tmp_path / "results")

    folder = tmp_path / "data" / "parsed" / "c1"
    assert sorted(p.name for p in folder.iterdir()) == [
        "example-ac.json",
        "example-handbook.json",
        "example-regulation.json",
    ]

    parsed = ParsedFile.model_validate_json((folder / "example-ac.json").read_text())
    assert parsed.config_hash == config_hash(config)
    assert parsed.document.document_id == "example-ac"
    assert parsed.document.passages[1].id == "example-ac#s1.0"


def test_the_report_is_written_under_the_run_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)

    returned = run_parse(settings, config, results_dir=tmp_path / "results")

    path = tmp_path / "results" / "v0" / "parse-report.json"
    report = ParseReport.model_validate_json(path.read_text())
    assert report == returned
    assert report.snapshot == "c1"
    assert report.config_hash == config_hash(config)
    assert [d.document_id for d in report.documents] == [
        "example-handbook",
        "example-regulation",
        "example-ac",
    ]
    assert report.documents[0].pages == 3
    assert report.documents[1].sections == 3


def test_a_second_run_gives_the_same_report_and_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)
    results = tmp_path / "results"
    report = results / "v0" / "parse-report.json"
    parsed = tmp_path / "data" / "parsed" / "c1" / "example-handbook.json"

    run_parse(settings, config, results_dir=results)
    first = (report.read_bytes(), parsed.read_bytes())
    run_parse(settings, config, results_dir=results)

    assert (report.read_bytes(), parsed.read_bytes()) == first


def test_files_of_documents_no_longer_in_the_snapshot_are_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)
    folder = tmp_path / "data" / "parsed" / "c1"
    folder.mkdir(parents=True)
    (folder / "old-document.json").write_text("{}")

    run_parse(settings, config, results_dir=tmp_path / "results")

    assert not (folder / "old-document.json").exists()


def test_a_document_outside_the_thresholds_stops_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch, min_characters=1500)

    with pytest.raises(ParseCheckError) as error:
        run_parse(settings, config, results_dir=tmp_path / "results")

    assert [p.split(":")[0] for p in error.value.problems] == [
        "example-regulation",
        "example-ac",
    ]
    assert "fewer than the minimum of 1500" in str(error.value)


def test_a_failed_check_writes_the_report_but_no_parsed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch, min_characters=1500)

    with pytest.raises(ParseCheckError):
        run_parse(settings, config, results_dir=tmp_path / "results")

    assert (tmp_path / "results" / "v0" / "parse-report.json").is_file()
    assert not (tmp_path / "data" / "parsed" / "c1").exists()


def test_a_missing_raw_file_stops_the_run_naming_the_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)
    (tmp_path / "data" / "raw" / "example-regulation.xml").unlink()

    with pytest.raises(ParseError, match="^example-regulation: .*hangar fetch"):
        run_parse(settings, config, results_dir=tmp_path / "results")
