import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from qdrant_client import QdrantClient

from hangar.core.chunks import Chunk, PassageRef, chunk_id
from hangar.core.config import PipelineConfig, config_hash
from hangar.core.parsed import PageLocation
from hangar.embedding.embedder import HashEmbedder
from hangar.indexing.index import VectorIndexError
from hangar.indexing.manifest import IndexManifest
from hangar.indexing.qdrant import QdrantIndex
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.embed import run_embed
from hangar.pipelines.index import run_index
from hangar.pipelines.settings import Settings, load_settings
from hangar.pipelines.vector_file import read_vectors, write_vectors

ROOT = Path(__file__).resolve().parents[3]
V0_CONFIG = ROOT / "configs" / "pipelines" / "v0.yaml"
COLLECTION = "c1__fixed512__bge-m3-dense"
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


def chunks_file(tmp_path: Path) -> Path:
    return tmp_path / "data" / "chunks" / "c1" / "fixed512" / "chunks.jsonl"


def vectors_folder(tmp_path: Path) -> Path:
    return tmp_path / "data" / "vectors" / "c1" / "fixed512" / "bge-m3-dense"


def write_chunks(tmp_path: Path, texts: list[str]) -> None:
    chunks, start = [], 0

    for text in texts:
        chunks.append(chunk(start, text))
        start += len(text)

    path = chunks_file(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(c.model_dump_json() for c in chunks) + "\n")


def setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, texts: list[str] = TEXTS
) -> tuple[Settings, PipelineConfig]:
    """Write a chunks file and embed it with the hash embedder."""
    monkeypatch.setenv("HANGAR_DATA_DIR", str(tmp_path / "data"))
    settings, config = load_settings(None), load_pipeline_config(V0_CONFIG)
    write_chunks(tmp_path, texts)
    run_embed(settings, config, embedder=HashEmbedder(dimension=8))

    return settings, config


def points(client: QdrantClient) -> list[tuple[Any, Any, Any]]:
    records, _ = client.scroll(
        COLLECTION, limit=100, with_payload=True, with_vectors=True
    )

    return sorted((r.id, r.payload, r.vector) for r in records)


class CountsOneTooMany(QdrantIndex):
    def count(self) -> int:
        return super().count() + 1


def test_each_chunk_becomes_one_point_with_its_chunk_as_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)
    client = QdrantClient(":memory:")

    run_index(settings, config, tmp_path / "results", QdrantIndex(client, COLLECTION))

    stored = points(client)
    assert len(stored) == 3
    payload_texts = sorted(payload["text"] for _, payload, _ in stored)
    assert payload_texts == sorted(TEXTS)


def test_the_manifest_records_the_collection_and_its_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)
    index = QdrantIndex(QdrantClient(":memory:"), COLLECTION)

    returned = run_index(settings, config, tmp_path / "results", index)

    path = tmp_path / "results" / "v0" / "index-manifest.json"
    manifest = IndexManifest.model_validate_json(path.read_text())
    assert manifest == returned
    assert manifest.collection == COLLECTION
    assert (manifest.snapshot, manifest.chunker_id, manifest.embedder_id) == (
        "c1",
        "fixed512",
        "bge-m3-dense",
    )
    assert (manifest.embedder.model_id, manifest.embedder.dimension) == ("hash", 8)
    assert (manifest.distance, manifest.points) == ("cosine", 3)
    assert manifest.qdrant_version == "1.20.0"
    assert manifest.config_hash == config_hash(config)
    vectors = vectors_folder(tmp_path) / "vectors.parquet"
    assert manifest.vectors_sha256 == hashlib.sha256(vectors.read_bytes()).hexdigest()
    chunks = chunks_file(tmp_path).read_bytes()
    assert manifest.chunks_sha256 == hashlib.sha256(chunks).hexdigest()
    assert "created" not in json.loads(path.read_text())


def test_running_index_twice_leaves_the_same_points_and_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)
    client = QdrantClient(":memory:")
    results = tmp_path / "results"
    manifest = results / "v0" / "index-manifest.json"

    run_index(settings, config, results, QdrantIndex(client, COLLECTION))
    first = (points(client), manifest.read_bytes())
    run_index(settings, config, results, QdrantIndex(client, COLLECTION))

    assert (points(client), manifest.read_bytes()) == first


def test_points_of_an_earlier_build_are_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)
    client = QdrantClient(":memory:")
    run_index(settings, config, tmp_path / "results", QdrantIndex(client, COLLECTION))

    setup(tmp_path, monkeypatch, texts=["eight nine"])
    run_index(settings, config, tmp_path / "results", QdrantIndex(client, COLLECTION))

    assert [payload["text"] for _, payload, _ in points(client)] == ["eight nine"]


def test_missing_vectors_stop_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HANGAR_DATA_DIR", str(tmp_path / "data"))
    write_chunks(tmp_path, TEXTS)
    index = QdrantIndex(QdrantClient(":memory:"), COLLECTION)

    with pytest.raises(VectorIndexError, match=f"^{COLLECTION}: .*run hangar embed"):
        run_index(
            load_settings(None),
            load_pipeline_config(V0_CONFIG),
            tmp_path / "results",
            index,
        )


def test_vectors_made_from_other_chunks_stop_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)
    write_chunks(tmp_path, ["eight nine"])
    index = QdrantIndex(QdrantClient(":memory:"), COLLECTION)

    with pytest.raises(VectorIndexError, match="another chunks file.*hangar embed"):
        run_index(settings, config, tmp_path / "results", index)


def test_a_chunk_without_a_vector_stops_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)
    path = vectors_folder(tmp_path) / "vectors.parquet"
    write_vectors(path, read_vectors(path)[:-1], dimension=8)
    index = QdrantIndex(QdrantClient(":memory:"), COLLECTION)

    with pytest.raises(VectorIndexError, match="3 chunks but 2 vectors"):
        run_index(settings, config, tmp_path / "results", index)


def test_a_point_count_that_disagrees_stops_the_run_without_a_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)
    index = CountsOneTooMany(QdrantClient(":memory:"), COLLECTION)

    with pytest.raises(VectorIndexError, match="4 points for 3 chunks"):
        run_index(settings, config, tmp_path / "results", index)

    assert not (tmp_path / "results" / "v0" / "index-manifest.json").exists()


def test_a_chunk_with_two_vectors_stops_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)
    path = vectors_folder(tmp_path) / "vectors.parquet"
    records = read_vectors(path)
    write_vectors(path, [*records[:-1], records[0]], dimension=8)
    index = QdrantIndex(QdrantClient(":memory:"), COLLECTION)

    with pytest.raises(VectorIndexError, match="more than one vector"):
        run_index(settings, config, tmp_path / "results", index)


def test_a_vector_for_an_unknown_chunk_stops_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, config = setup(tmp_path, monkeypatch)
    path = vectors_folder(tmp_path) / "vectors.parquet"
    records = read_vectors(path)
    stranger = records[-1].model_copy(update={"chunk_id": "0" * 16})
    write_vectors(path, [*records[:-1], stranger], dimension=8)
    index = QdrantIndex(QdrantClient(":memory:"), COLLECTION)

    with pytest.raises(VectorIndexError, match="1 of 3 chunks have no vector"):
        run_index(settings, config, tmp_path / "results", index)
