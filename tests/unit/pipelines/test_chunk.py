import hashlib
import json
from pathlib import Path

import pytest

from hangar.chunking.chunker import ChunkError
from hangar.chunking.fixed import FixedTokenChunker
from hangar.chunking.tokens import WhitespaceCounter
from hangar.core.chunks import Chunk, ChunksMeta
from hangar.core.config import ChunkingConfig, PipelineConfig, config_hash
from hangar.core.parsed import PageLocation, ParsedDocument, ParsedFile, Passage
from hangar.pipelines.chunk import run_chunk
from hangar.pipelines.settings import Settings
from tests.fixture_corpus import FixtureCorpus

FAKE_SHA256 = "0123456789abcdef" * 4

# Two one-page documents: 5 words and 2 words.
TEXTS = {
    "example-handbook": "one two three four five",
    "example-ac": "six seven",
}


def parsed_file(document_id: str, text: str, config: PipelineConfig) -> ParsedFile:
    location = PageLocation(page_index=1, page_label=None)
    passage = Passage(id=f"{document_id}#p1", location=location, start=0, end=len(text))
    document = ParsedDocument(
        document_id=document_id,
        source_sha256=FAKE_SHA256,
        parser={"name": "example-parser", "version": "1.0"},
        text=text,
        passages=[passage],
    )

    return ParsedFile(config_hash=config_hash(config), document=document)


def setup(
    tmp_path: Path, fixture_corpus: FixtureCorpus
) -> tuple[Settings, PipelineConfig]:
    """Write the parsed files of the snapshot, and point the settings at them."""
    config = fixture_corpus.config()
    folder = tmp_path / "data" / "parsed" / "c1"
    folder.mkdir(parents=True)

    for document_id, text in TEXTS.items():
        content = parsed_file(document_id, text, config).model_dump_json()
        (folder / f"{document_id}.json").write_text(content + "\n")

    return fixture_corpus.settings(), config


def word_chunker(size: int = 3) -> FixedTokenChunker:
    config = ChunkingConfig(
        type="fixed_tokens", size=size, overlap=0, tokenizer="embedder"
    )

    return FixedTokenChunker(WhitespaceCounter(), config)


def read_chunks(path: Path) -> list[Chunk]:
    lines = path.read_text().splitlines()

    return [Chunk.model_validate_json(line) for line in lines]


def test_chunks_of_every_document_are_written_in_document_id_order(
    tmp_path: Path, fixture_corpus: FixtureCorpus
) -> None:
    settings, config = setup(tmp_path, fixture_corpus)

    run_chunk(settings, config, chunker=word_chunker())

    path = tmp_path / "data" / "chunks" / "c1" / "fixed3" / "chunks.jsonl"
    chunks = read_chunks(path)
    assert [(c.document_id, c.text) for c in chunks] == [
        ("example-ac", "six seven"),
        ("example-handbook", "one two three "),
        ("example-handbook", "four five"),
    ]


def test_meta_records_the_inputs_the_tokenizer_and_the_counts(
    tmp_path: Path, fixture_corpus: FixtureCorpus
) -> None:
    settings, config = setup(tmp_path, fixture_corpus)
    parsed = tmp_path / "data" / "parsed" / "c1" / "example-ac.json"

    returned = run_chunk(settings, config, chunker=word_chunker())

    path = tmp_path / "data" / "chunks" / "c1" / "fixed3" / "meta.json"
    meta = ChunksMeta.model_validate_json(path.read_text())
    assert meta == returned
    assert meta.snapshot == "c1"
    assert meta.chunker_id == "fixed3"
    assert meta.config_hash == config_hash(config)
    assert meta.tokenizer.model == config.embedding.model
    assert meta.tokenizer.revision == config.embedding.revision
    assert sorted(meta.parsed_files) == ["example-ac", "example-handbook"]
    assert (
        meta.parsed_files["example-ac"]
        == hashlib.sha256(parsed.read_bytes()).hexdigest()
    )
    assert (meta.chunks, meta.tokens) == (3, 7)


def test_meta_holds_nothing_that_changes_between_identical_runs(
    tmp_path: Path, fixture_corpus: FixtureCorpus
) -> None:
    settings, config = setup(tmp_path, fixture_corpus)
    folder = tmp_path / "data" / "chunks" / "c1" / "fixed3"

    run_chunk(settings, config, chunker=word_chunker())
    first = [(folder / name).read_bytes() for name in ("chunks.jsonl", "meta.json")]
    run_chunk(settings, config, chunker=word_chunker())
    second = [(folder / name).read_bytes() for name in ("chunks.jsonl", "meta.json")]

    assert first == second
    assert set(json.loads(first[1])) == {
        "snapshot",
        "chunker_id",
        "config_hash",
        "tokenizer",
        "parsed_files",
        "chunks",
        "tokens",
    }


def test_a_missing_parsed_folder_stops_the_run(
    tmp_path: Path, fixture_corpus: FixtureCorpus
) -> None:
    settings, config = fixture_corpus.settings(), fixture_corpus.config()

    with pytest.raises(ChunkError, match="run hangar parse first"):
        run_chunk(settings, config, chunker=word_chunker())
