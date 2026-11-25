from pathlib import Path

import pytest

from hangar.chunking.chunker import ChunkError
from hangar.core.chunks import Chunk
from hangar.pipelines.chunk_file import read_chunks
from tests.builders import chunk


def write(path: Path, chunks: list[Chunk]) -> None:
    path.write_text("\n".join(c.model_dump_json() for c in chunks) + "\n")


def test_chunks_are_read_in_file_order(tmp_path: Path) -> None:
    chunks = [chunk("one two "), chunk("three", start=8)]
    path = tmp_path / "chunks.jsonl"
    write(path, chunks)

    assert read_chunks(path) == chunks


def test_a_chunk_listed_twice_is_refused(tmp_path: Path) -> None:
    twice = chunk("one two ")
    path = tmp_path / "chunks.jsonl"
    write(path, [twice, twice])

    with pytest.raises(ChunkError, match=f"^{twice.id}: .*more than once"):
        read_chunks(path)
