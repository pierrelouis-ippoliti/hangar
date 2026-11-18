import hashlib
from collections.abc import Sequence
from pathlib import Path

import pytest

from hangar.chunking.chunker import ChunkError
from hangar.core.chunks import Chunk, PassageRef, chunk_id
from hangar.core.config import PipelineConfig, config_hash
from hangar.core.parsed import PageLocation
from hangar.core.vectors import VectorsMeta
from hangar.embedding.embedder import EmbedError, HashEmbedder
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.embed import run_embed
from hangar.pipelines.settings import Settings, load_settings
from hangar.pipelines.vector_file import read_vectors

ROOT = Path(__file__).resolve().parents[3]
V0_CONFIG = ROOT / "configs" / "pipelines" / "v0.yaml"
TEXTS = ["one two three ", "four five", "six seven"]


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


def chunks_folder(tmp_path: Path) -> Path:
    return tmp_path / "data" / "chunks" / "c1" / "fixed512"


def vectors_folder(tmp_path: Path) -> Path:
    return tmp_path / "data" / "vectors" / "c1" / "fixed512" / "bge-m3-dense"


def setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, chunks: list[Chunk] | None = None
) -> tuple[Settings, PipelineConfig]:
    """Write a chunks file, and point the settings at it."""
    if chunks is None:
        starts = [0, 14, 23]
        chunks = [chunk(start, text) for start, text in zip(starts, TEXTS, strict=True)]

    folder = chunks_folder(tmp_path)
    folder.mkdir(parents=True)
    lines = "\n".join(c.model_dump_json() for c in chunks)
    (folder / "chunks.jsonl").write_text(lines + "\n")
    monkeypatch.setenv("HANGAR_DATA_DIR", str(tmp_path / "data"))

    return load_settings(None), load_pipeline_config(V0_CONFIG)


class DropsTheLastVector(HashEmbedder):
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return super().embed_documents(texts)[:-1]


class ReportsTheWrongDimension(HashEmbedder):
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [vector[:-1] for vector in super().embed_documents(texts)]


def test_each_chunk_gets_its_vector_in_chunk_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)
    embedder = HashEmbedder(dimension=8)

    run_embed(settings, config, embedder=embedder)

    records = read_vectors(vectors_folder(tmp_path) / "vectors.parquet")
    chunks = (chunks_folder(tmp_path) / "chunks.jsonl").read_text().splitlines()
    assert [r.chunk_id for r in records] == [
        Chunk.model_validate_json(line).id for line in chunks
    ]
    assert {(r.model_id, r.revision) for r in records} == {("hash", "1")}
    for record, text in zip(records, TEXTS, strict=True):
        assert record.vector == pytest.approx(embedder.embed_query(text), abs=1e-6)


def test_meta_records_the_input_the_embedder_and_the_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)
    chunks_file = chunks_folder(tmp_path) / "chunks.jsonl"

    returned = run_embed(settings, config, embedder=HashEmbedder(dimension=8))

    path = vectors_folder(tmp_path) / "meta.json"
    meta = VectorsMeta.model_validate_json(path.read_text())
    assert meta == returned
    assert (meta.snapshot, meta.chunker_id, meta.embedder_id) == (
        "c1",
        "fixed512",
        "bge-m3-dense",
    )
    assert meta.config_hash == config_hash(config)
    assert meta.embedder.model_dump() == {
        "model_id": "hash",
        "revision": "1",
        "dimension": 8,
        "normalized": True,
    }
    assert meta.chunks_sha256 == hashlib.sha256(chunks_file.read_bytes()).hexdigest()
    assert meta.vectors == 3


def test_a_second_run_writes_the_same_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)
    folder = vectors_folder(tmp_path)
    names = ("vectors.parquet", "meta.json")

    run_embed(settings, config, embedder=HashEmbedder(dimension=8))
    first = [(folder / name).read_bytes() for name in names]
    run_embed(settings, config, embedder=HashEmbedder(dimension=8))

    assert [(folder / name).read_bytes() for name in names] == first


def test_a_missing_chunks_file_stops_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HANGAR_DATA_DIR", str(tmp_path / "data"))
    config = load_pipeline_config(V0_CONFIG)

    with pytest.raises(EmbedError, match="run hangar chunk first"):
        run_embed(load_settings(None), config, embedder=HashEmbedder())


def test_a_chunk_listed_twice_stops_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    twice = chunk(0, "one two three ")
    settings, config = setup(tmp_path, monkeypatch, chunks=[twice, twice])

    with pytest.raises(ChunkError, match=f"^{twice.id}: .*more than once"):
        run_embed(settings, config, embedder=HashEmbedder())


def test_a_missing_vector_stops_the_run_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)

    with pytest.raises(EmbedError, match="2 vectors for 3 chunks"):
        run_embed(settings, config, embedder=DropsTheLastVector())

    assert not vectors_folder(tmp_path).exists()


def test_a_vector_of_the_wrong_dimension_stops_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)

    with pytest.raises(EmbedError, match="7 values, not 8"):
        run_embed(settings, config, embedder=ReportsTheWrongDimension(dimension=8))
