from pathlib import Path

import pytest

from hangar.core.config import PipelineConfig
from hangar.pipelines.parse import run_parse
from hangar.pipelines.passage import (
    PassageError,
    format_locations,
    format_passage,
    load_parsed_document,
)
from hangar.pipelines.settings import Settings
from tests.fixture_corpus import FixtureCorpus


@pytest.fixture
def parsed(
    fixture_corpus: FixtureCorpus, tmp_path: Path
) -> tuple[Settings, PipelineConfig]:
    """Parse the fixture corpus into the test's data folder."""
    fixture_corpus.copy_raw()
    settings, config = fixture_corpus.settings(), fixture_corpus.config()
    run_parse(settings, config, results_dir=tmp_path / "results")

    return settings, config


def test_load_parsed_document_reads_the_snapshot_file(
    parsed: tuple[Settings, PipelineConfig],
) -> None:
    document = load_parsed_document(*parsed, "example-ac")

    assert document.document_id == "example-ac"


def test_load_parsed_document_asks_for_parse_when_the_file_is_missing(
    fixture_corpus: FixtureCorpus,
) -> None:
    with pytest.raises(PassageError, match="run hangar parse first"):
        load_parsed_document(
            fixture_corpus.settings(), fixture_corpus.config(), "example-ac"
        )


def test_a_page_shows_its_evidence_location_printed_label_and_text(
    parsed: tuple[Settings, PipelineConfig],
) -> None:
    document = load_parsed_document(*parsed, "example-handbook")

    lines = format_passage(document, "p2").splitlines()

    assert lines[:4] == [
        "passage:  example-handbook#p2",
        'evidence: "document_id": "example-handbook", "location": "p2"',
        "page:     index 2, printed label 1-14",
        "",
    ]
    assert lines[4] == "1-14"
    assert lines[5].startswith("Immediately after the engine starts")


def test_a_section_shows_its_heading_path(
    parsed: tuple[Settings, PipelineConfig],
) -> None:
    document = load_parsed_document(*parsed, "example-ac")

    lines = format_passage(document, "s1.1").splitlines()

    assert lines[1] == 'evidence: "document_id": "example-ac", "location": "s1.1"'
    assert lines[2] == (
        "section:  Advisory Circular (AC) No. 571-999 > 1.0 Introduction > 1.1 Purpose"
    )


def test_an_unknown_location_is_refused_with_a_hint(
    parsed: tuple[Settings, PipelineConfig],
) -> None:
    document = load_parsed_document(*parsed, "example-handbook")

    with pytest.raises(PassageError, match="hangar passage example-handbook"):
        format_passage(document, "1-14")


def test_locations_list_every_passage_with_its_label_or_heading(
    parsed: tuple[Settings, PipelineConfig],
) -> None:
    handbook = load_parsed_document(*parsed, "example-handbook")
    ac = load_parsed_document(*parsed, "example-ac")

    assert format_locations(handbook).splitlines() == [
        "p1  printed label 1-13",
        "p2  printed label 1-14",
        "p3  printed label 1-15",
    ]
    # The column is as wide as the document's longest location.
    assert [
        line.split(maxsplit=1) for line in format_locations(ac).splitlines()[:2]
    ] == [
        ["front", "Advisory Circular (AC) No. 571-999"],
        ["s1.0", "1.0 Introduction"],
    ]
