from pathlib import Path

import pytest

from hangar.chunking.chunker import ChunkError
from hangar.core.chunks import Chunk, PassageRef, chunk_id
from hangar.core.parsed import PageLocation
from hangar.pipelines.chunk_file import read_chunks


def chunk(start: int, text: str) -> Chunk:
    end = start + len(text)

    return Chunk(
        id=chunk_id("example-handbook", "fixed512", start, end),
        document_id="example-handbook",
        chunker_id="fixed512",
        start=start,
        end=end,
        text=text,
        token_count=len(text.split()),
        passages=[
            PassageRef(
                id="example-handbook#p1",
                location=PageLocation(page_index=1, page_label=None),
            )
        ],
    )


def write(path: Path, chunks: list[Chunk]) -> None:
    path.write_text("\n".join(c.model_dump_json() for c in chunks) + "\n")


def test_chunks_are_read_in_file_order(tmp_path: Path) -> None:
    chunks = [chunk(0, "one two "), chunk(8, "three")]
    path = tmp_path / "chunks.jsonl"
    write(path, chunks)

    assert read_chunks(path) == chunks


def test_a_chunk_listed_twice_is_refused(tmp_path: Path) -> None:
    twice = chunk(0, "one two ")
    path = tmp_path / "chunks.jsonl"
    write(path, [twice, twice])

    with pytest.raises(ChunkError, match=f"^{twice.id}: .*more than once"):
        read_chunks(path)
