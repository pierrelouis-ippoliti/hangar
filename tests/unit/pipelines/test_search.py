from pathlib import Path

import pytest

from hangar.core.chunks import PassageRef
from hangar.core.retrieval import ScoredChunk
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.search import format_results, run_search
from hangar.pipelines.settings import load_settings
from hangar.retrieval.retriever import FixedRetriever
from tests.builders import chunk, page, scored, section

ROOT = Path(__file__).resolve().parents[3]
V0_CONFIG = ROOT / "configs" / "pipelines" / "v0.yaml"


def result(passages: list[PassageRef], text: str = "Torque the bolts.") -> ScoredChunk:
    return scored(chunk(text, passages=passages), score=0.71234)


def first_line(found: ScoredChunk) -> str:
    return format_results([found]).splitlines()[0]


def test_search_returns_what_the_retriever_finds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HANGAR_DATA_DIR", str(tmp_path / "data"))
    chunks = [chunk(), chunk(passages=[section("571.10")])]
    retriever = FixedRetriever(chunks)

    results = run_search(
        load_settings(None),
        load_pipeline_config(V0_CONFIG),
        "How tight should the bolts be?",
        retriever=retriever,
    )

    assert [r.chunk for r in results] == chunks


def test_a_result_shows_rank_score_document_and_page_with_its_label() -> None:
    assert first_line(result([page(142, "7-12")])) == (
        "1. 0.712  example-handbook, p. 142 (7-12)"
    )


def test_a_page_without_a_printed_label_shows_its_index_only() -> None:
    assert first_line(result([page(142)])).endswith("example-handbook, p. 142")


def test_a_chunk_across_pages_shows_its_first_and_last_page() -> None:
    line = first_line(result([page(141, "7-11"), page(142, "7-12")]))

    assert line.endswith("p. 141 (7-11) to p. 142 (7-12)")


def test_sections_show_their_number_and_front_matter_its_name() -> None:
    assert first_line(result([section("571.10")])).endswith("tc-std-571, § 571.10")
    assert first_line(result([section(None), section("1.0")])).endswith(
        "tc-std-571, front matter to § 1.0"
    )


def test_the_excerpt_collapses_whitespace_and_is_cut_at_160_characters() -> None:
    text = "Torque\nthe   bolts. " + "x" * 300
    excerpt = format_results([result([page(1)], text)]).splitlines()[1]

    assert excerpt.startswith("   Torque the bolts. xxx")
    assert len(excerpt) == 3 + 160 + 1
    assert excerpt.endswith("…")


def test_a_short_excerpt_is_shown_whole() -> None:
    excerpt = format_results([result([page(1)])]).splitlines()[1]

    assert excerpt == "   Torque the bolts."


def test_results_are_separated_by_a_blank_line() -> None:
    results = FixedRetriever([chunk(), chunk(passages=[page(2)])]).retrieve("q")

    lines = format_results(results).splitlines()

    assert lines[2] == ""
    assert lines[3].startswith("2. 0.500  example-handbook, p. 2")


def test_no_result_says_so() -> None:
    assert format_results([]) == "No chunk found."
