from pathlib import Path

import pytest

from hangar.core.vectors import VectorRecord
from hangar.embedding.embedder import EmbedError
from hangar.pipelines.vector_file import read_vectors, write_vectors


def record(chunk_id: str, vector: tuple[float, ...]) -> VectorRecord:
    return VectorRecord(
        chunk_id=chunk_id, model_id="BAAI/bge-m3", revision="b" * 40, vector=vector
    )


RECORDS = [
    record("0123456789abcdef", (0.5, 0.75)),
    record("fedcba9876543210", (1.0, 0.0)),
]


def test_records_survive_a_round_trip_in_order(tmp_path: Path) -> None:
    path = tmp_path / "vectors.parquet"

    write_vectors(path, RECORDS, dimension=2)

    assert read_vectors(path) == RECORDS


def test_values_are_stored_as_32_bit_floats(tmp_path: Path) -> None:
    path = tmp_path / "vectors.parquet"

    write_vectors(path, [record("0123456789abcdef", (0.1, 0.2))], dimension=2)

    (read,) = read_vectors(path)
    assert read.vector != (0.1, 0.2)
    assert read.vector == pytest.approx((0.1, 0.2), abs=1e-7)


def test_a_vector_of_another_dimension_is_refused(tmp_path: Path) -> None:
    with pytest.raises(EmbedError, match="fedcba9876543210: .* 3 values, not 2"):
        write_vectors(
            tmp_path / "vectors.parquet",
            [RECORDS[0], record("fedcba9876543210", (1.0, 0.0, 0.0))],
            dimension=2,
        )
