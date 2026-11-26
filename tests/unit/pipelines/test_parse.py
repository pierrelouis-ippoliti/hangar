from pathlib import Path
from typing import Any

import pytest

from hangar.core.config import PipelineConfig, config_hash
from hangar.core.parsed import ParsedFile
from hangar.parsing.parser import ParseError
from hangar.parsing.report import ParseCheckError, ParseReport
from hangar.pipelines.parse import run_parse
from hangar.pipelines.settings import Settings
from tests.fixture_corpus import FixtureCorpus


def setup(
    fixture_corpus: FixtureCorpus, **checks: Any
) -> tuple[Settings, PipelineConfig]:
    """Copy the fixture corpus into the raw folder, and load its config."""
    fixture_corpus.copy_raw()

    return fixture_corpus.settings(), fixture_corpus.config(**checks)


def test_every_document_is_parsed_into_the_snapshot_folder(
    tmp_path: Path, fixture_corpus: FixtureCorpus
) -> None:
    settings, config = setup(fixture_corpus)

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
    tmp_path: Path, fixture_corpus: FixtureCorpus
) -> None:
    settings, config = setup(fixture_corpus)

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
    tmp_path: Path, fixture_corpus: FixtureCorpus
) -> None:
    settings, config = setup(fixture_corpus)
    results = tmp_path / "results"
    report = results / "v0" / "parse-report.json"
    parsed = tmp_path / "data" / "parsed" / "c1" / "example-handbook.json"

    run_parse(settings, config, results_dir=results)
    first = (report.read_bytes(), parsed.read_bytes())
    run_parse(settings, config, results_dir=results)

    assert (report.read_bytes(), parsed.read_bytes()) == first


def test_files_of_documents_no_longer_in_the_snapshot_are_removed(
    tmp_path: Path, fixture_corpus: FixtureCorpus
) -> None:
    settings, config = setup(fixture_corpus)
    folder = tmp_path / "data" / "parsed" / "c1"
    folder.mkdir(parents=True)
    (folder / "old-document.json").write_text("{}")

    run_parse(settings, config, results_dir=tmp_path / "results")

    assert not (folder / "old-document.json").exists()


def test_a_document_outside_the_thresholds_stops_the_run(
    tmp_path: Path, fixture_corpus: FixtureCorpus
) -> None:
    settings, config = setup(fixture_corpus, min_characters=1500)

    with pytest.raises(ParseCheckError) as error:
        run_parse(settings, config, results_dir=tmp_path / "results")

    assert [p.split(":")[0] for p in error.value.problems] == [
        "example-regulation",
        "example-ac",
    ]
    assert "fewer than the minimum of 1500" in str(error.value)


def test_a_failed_check_writes_the_report_but_no_parsed_files(
    tmp_path: Path, fixture_corpus: FixtureCorpus
) -> None:
    settings, config = setup(fixture_corpus, min_characters=1500)

    with pytest.raises(ParseCheckError):
        run_parse(settings, config, results_dir=tmp_path / "results")

    assert (tmp_path / "results" / "v0" / "parse-report.json").is_file()
    assert not (tmp_path / "data" / "parsed" / "c1").exists()


def test_a_missing_raw_file_stops_the_run_naming_the_document(
    tmp_path: Path, fixture_corpus: FixtureCorpus
) -> None:
    settings, config = setup(fixture_corpus)
    (tmp_path / "data" / "raw" / "example-regulation.xml").unlink()

    with pytest.raises(ParseError, match="^example-regulation: .*hangar fetch"):
        run_parse(settings, config, results_dir=tmp_path / "results")
