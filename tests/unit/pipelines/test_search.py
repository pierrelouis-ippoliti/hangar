from pathlib import Path

import pytest

from hangar.core.chunks import Chunk, PassageRef, chunk_id
from hangar.core.parsed import PageLocation, SectionLocation
from hangar.core.retrieval import ScoredChunk
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.search import format_results, run_search
from hangar.pipelines.settings import load_settings
from hangar.retrieval.retriever import FixedRetriever

ROOT = Path(__file__).resolve().parents[3]
V0_CONFIG = ROOT / "configs" / "pipelines" / "v0.yaml"


def page(index: int, label: str | None = None) -> PassageRef:
    return PassageRef(
        id=f"example-handbook#p{index}",
        location=PageLocation(page_index=index, page_label=label),
    )


def section(label: str | None) -> PassageRef:
    return PassageRef(
        id=f"tc-std-571#s{label}" if label else "tc-std-571#front",
        location=SectionLocation(label=label, heading_path=("Standard 571",)),
    )


def chunk(passages: list[PassageRef], text: str = "Torque the bolts.") -> Chunk:
    document_id = passages[0].id.split("#")[0]

    return Chunk(
        id=chunk_id(document_id, "fixed512", 0, len(text)),
        document_id=document_id,
        chunker_id="fixed512",
        start=0,
        end=len(text),
        text=text,
        token_count=len(text.split()),
        passages=passages,
    )


def result(passages: list[PassageRef], text: str = "Torque the bolts.") -> ScoredChunk:
    return ScoredChunk(
        chunk=chunk(passages, text), score=0.71234, rank=1, retriever_id="dense"
    )


def first_line(scored: ScoredChunk) -> str:
    return format_results([scored]).splitlines()[0]


def test_search_returns_what_the_retriever_finds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HANGAR_DATA_DIR", str(tmp_path / "data"))
    chunks = [chunk([page(1)]), chunk([section("571.10")])]
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
    results = FixedRetriever([chunk([page(1)]), chunk([page(2)])]).retrieve("q")

    lines = format_results(results).splitlines()

    assert lines[2] == ""
    assert lines[3].startswith("2. 0.500  example-handbook, p. 2")


def test_no_result_says_so() -> None:
    assert format_results([]) == "No chunk found."
