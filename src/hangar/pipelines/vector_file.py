"""
The vectors file: one Parquet row per chunk, written by embed, read by index.

Each row holds the chunk ID, the model ID, its revision, and the vector as
32-bit floats, so a 1,024-value BGE-M3 vector takes 4 KB.
"""

from collections.abc import Sequence
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from hangar.core.vectors import VectorRecord
from hangar.embedding.embedder import EmbedError


def write_vectors(path: Path, records: Sequence[VectorRecord], dimension: int) -> None:
    """
    Write vector records to a Parquet file, in their order.

    Args:
        path: The file to write. An existing file is overwritten.
        records: The records to write.
        dimension: How many values every vector must have.

    Raises:
        EmbedError: If a vector has another number of values. The message
            starts with its chunk ID.
    """
    for record in records:
        if len(record.vector) != dimension:
            raise EmbedError(
                f"{record.chunk_id}: the vector has {len(record.vector)} values, "
                f"not {dimension}"
            )

    schema = pa.schema(
        [
            ("chunk_id", pa.string()),
            ("model_id", pa.string()),
            ("revision", pa.string()),
            ("vector", pa.list_(pa.float32(), dimension)),
        ]
    )
    table = pa.table(
        {
            "chunk_id": [r.chunk_id for r in records],
            "model_id": [r.model_id for r in records],
            "revision": [r.revision for r in records],
            "vector": [list(r.vector) for r in records],
        },
        schema=schema,
    )
    pq.write_table(table, path)


def read_vectors(path: Path) -> list[VectorRecord]:
    """
    Read the vector records of a Parquet file.

    Args:
        path: The file written by ``write_vectors``.

    Returns:
        The records, in file order.
    """
    rows = pq.read_table(path).to_pylist()

    return [VectorRecord.model_validate(row) for row in rows]
