"""The chunks file: one chunk per line, written by chunk, read by embed and index."""

from pathlib import Path

from hangar.chunking.chunker import ChunkError
from hangar.core.chunks import Chunk


def read_chunks(path: Path) -> list[Chunk]:
    """
    Read the chunks of a ``chunks.jsonl`` file.

    Args:
        path: The file written by ``hangar chunk``.

    Returns:
        The chunks, in file order.

    Raises:
        ChunkError: If a chunk is listed more than once. The message starts
            with its ID.
    """
    chunks = []
    seen = set()

    for line in path.read_text(encoding="utf-8").splitlines():
        chunk = Chunk.model_validate_json(line)

        if chunk.id in seen:
            raise ChunkError(f"{chunk.id}: the chunk is listed more than once")

        seen.add(chunk.id)
        chunks.append(chunk)

    return chunks
