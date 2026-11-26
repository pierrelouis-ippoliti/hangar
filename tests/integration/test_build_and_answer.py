"""
The whole build and answering path on the fixture corpus, fully offline.

fetch → parse → chunk → embed → index → ask, with the local-copy downloader,
a chunker that counts words, the hash embedder, Qdrant in memory and the
fake language model. No network, no real model, no secret.
"""

import datetime
import json
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from qdrant_client import QdrantClient

from hangar.chunking.fixed import FixedTokenChunker
from hangar.chunking.tokens import WhitespaceCounter
from hangar.core.chunks import Chunk, chunker_id
from hangar.core.config import PipelineConfig, config_hash
from hangar.core.parsed import ParsedFile
from hangar.core.records import AnswerRecord, RunRecord
from hangar.core.vectors import embedder_id
from hangar.embedding.embedder import HashEmbedder
from hangar.generation.llm import FakeLlmClient
from hangar.generation.presentation import STUDY_AID_NOTICE
from hangar.indexing.naming import collection_name
from hangar.indexing.qdrant import QdrantIndex
from hangar.observability.logs import new_run_id
from hangar.pipelines.ask import run_ask
from hangar.pipelines.chunk import run_chunk
from hangar.pipelines.chunk_file import read_chunks
from hangar.pipelines.embed import run_embed
from hangar.pipelines.fetch import run_fetch
from hangar.pipelines.index import run_index
from hangar.pipelines.parse import run_parse
from hangar.pipelines.registry import build_retriever
from tests.fixture_corpus import ROOT, FixtureCorpus

QUESTION = "When must the maintenance records be kept?"
# Cites each of the five sources the retriever returns, in order.
ANSWER = "Keep them [1]. Check them [2]. Sign them [3]. File them [4]. Show them [5]."


@dataclass(frozen=True)
class Answered:
    """
    What the whole path left behind: its configuration, its chunks and
    parsed files, the screen text, and the recorded answer and run.
    """

    config: PipelineConfig
    chunks: dict[str, Chunk]
    parsed: dict[str, ParsedFile]
    screen: str
    answer_line: str
    answer: AnswerRecord
    run: RunRecord


@pytest.fixture
def answered(
    fixture_corpus: FixtureCorpus, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Answered]:
    """
    Build the fixture corpus, then ask one question and record the answer.
    """
    # From the repository root, ask finds prompts/ and the git commit.
    monkeypatch.chdir(ROOT)
    settings, config = fixture_corpus.settings(), fixture_corpus.config()
    results = fixture_corpus.folder / "results"
    embedder = HashEmbedder()
    client = QdrantClient(":memory:")
    name = collection_name(
        config.corpus.snapshot,
        chunker_id(config.chunking),
        embedder_id(config.embedding),
    )
    index = QdrantIndex(client, name)

    run_fetch(settings, config, fixture_corpus.downloader)
    run_parse(settings, config, results_dir=results)
    run_chunk(settings, config, FixedTokenChunker(WhitespaceCounter(), config.chunking))
    run_embed(settings, config, embedder)
    run_index(settings, config, results, index)

    run_id = new_run_id(config_hash(config), datetime.datetime.now(datetime.UTC))
    screen = run_ask(
        settings,
        config,
        QUESTION,
        run_id,
        record=True,
        retriever=build_retriever(config.retrieval, embedder, index),
        llm=FakeLlmClient(ANSWER),
    )

    data = fixture_corpus.data_dir
    chunks_file = data / "chunks" / "c1" / "fixed512" / "chunks.jsonl"
    parsed_dir = data / "parsed" / "c1"
    run_dir = data / "runs" / run_id
    (answer_line,) = (run_dir / "answers.jsonl").read_text().splitlines()

    yield Answered(
        config=config,
        chunks={chunk.id: chunk for chunk in read_chunks(chunks_file)},
        parsed={
            path.stem: ParsedFile.model_validate_json(path.read_text())
            for path in parsed_dir.glob("*.json")
        },
        screen=screen,
        answer_line=answer_line,
        answer=AnswerRecord.model_validate_json(answer_line),
        run=RunRecord.model_validate_json((run_dir / "run.json").read_text()),
    )
    client.close()


def overlapping_passages(parsed: ParsedFile, start: int, end: int) -> list[str]:
    """
    The IDs of the passages that share at least one character with a span.
    """
    return [
        passage.id
        for passage in parsed.document.passages
        if passage.start < end and start < passage.end
    ]


def strings(value: object) -> Iterator[str]:
    """
    Every string in a JSON value, however deeply nested.
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def test_every_document_is_built_and_the_answer_uses_the_index(
    answered: Answered,
) -> None:
    documents = {chunk.document_id for chunk in answered.chunks.values()}
    retrieved = [ref.chunk_id for ref in answered.answer.scored_chunks]

    assert sorted(answered.parsed) == sorted(documents)
    assert sorted(documents) == ["example-ac", "example-handbook", "example-regulation"]
    assert len(retrieved) == answered.config.retrieval.top_k
    assert set(retrieved) <= set(answered.chunks)


def test_each_citation_maps_to_the_pages_or_sections_of_its_chunk(
    answered: Answered,
) -> None:
    answer = answered.answer

    assert [c.marker for c in answer.citations] == [1, 2, 3, 4, 5]

    for citation in answer.citations:
        source = answer.scored_chunks[citation.marker - 1]
        assert citation.valid
        assert citation.chunk_id == source.chunk_id

        chunk = answered.chunks[source.chunk_id]
        parsed = answered.parsed[chunk.document_id]
        assert citation.document_id == chunk.document_id
        assert parsed.document.text[chunk.start : chunk.end] == chunk.text
        assert [p.id for p in citation.passages] == overlapping_passages(
            parsed, chunk.start, chunk.end
        )


def test_the_screen_shows_pages_and_sections_and_ends_with_the_notice(
    answered: Answered,
) -> None:
    # The hash embedder ranks the chunks by chance, but always the same way:
    # this question gets the first handbook page, printed 1-13, first, and the
    # one regulation chunk, which holds the three kept sections, third.
    assert "\n[1] example-handbook, p. 1 (1-13)\n" in answered.screen
    assert "\n[3] example-regulation, § 571.01 to § 573.01\n" in answered.screen
    assert answered.screen.endswith(STUDY_AID_NOTICE)


def test_the_recorded_answer_holds_no_chunk_text(answered: Answered) -> None:
    recorded = "\n".join(strings(json.loads(answered.answer_line)))

    for chunk in answered.chunks.values():
        # Every 100-character stretch, starting every 50 characters.
        for start in range(0, max(len(chunk.text) - 100, 0) + 1, 50):
            assert chunk.text[start : start + 100] not in recorded


def test_the_run_record_carries_the_provenance(answered: Answered) -> None:
    run = answered.run

    assert run.run_id == answered.answer.run_id
    assert run.config_hash == config_hash(answered.config)
    assert run.code is not None
    assert len(run.code.commit) == 40
    assert isinstance(run.code.dirty, bool)
    assert run.totals.answers == 1
