from pathlib import Path

import pytest
import yaml

from hangar.core.errors import ConfigError
from hangar.corpus.manifest import load_snapshot

FIXTURE_MANIFEST = (
    Path(__file__).resolve().parents[2] / "fixtures" / "corpus" / "manifest.yaml"
)


def write_manifest(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def fixture_data() -> dict[str, object]:
    data = yaml.safe_load(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_snapshot_holds_the_active_documents_in_manifest_order() -> None:
    documents = load_snapshot(FIXTURE_MANIFEST, "c1")

    assert [d.id for d in documents] == [
        "example-handbook",
        "example-regulation",
        "example-standard",
    ]


def test_cancelled_documents_are_left_out_of_the_snapshot() -> None:
    documents = load_snapshot(FIXTURE_MANIFEST, "c1")

    assert "example-ac-cancelled" not in {d.id for d in documents}
    assert all(d.status == "active" for d in documents)


def test_yaml_values_arrive_with_their_types() -> None:
    regulation = load_snapshot(FIXTURE_MANIFEST, "c1")[1]

    assert regulation.edition == "2026"
    assert regulation.content_date.isoformat() == "2026-06-18"


def test_other_snapshot_is_refused_with_the_file_and_field() -> None:
    with pytest.raises(ConfigError) as error_info:
        load_snapshot(FIXTURE_MANIFEST, "c2")

    assert str(error_info.value).startswith(f"{FIXTURE_MANIFEST}: snapshot: ")
    assert "c2" in str(error_info.value)


def test_invalid_entry_error_names_the_file_and_the_field(tmp_path: Path) -> None:
    data = fixture_data()
    documents = data["documents"]
    assert isinstance(documents, list)
    documents[2]["sha256"] = "not-a-hash"
    path = write_manifest(tmp_path, data)

    with pytest.raises(ConfigError) as error_info:
        load_snapshot(path, "c1")

    assert str(error_info.value).startswith(f"{path}: documents[2].sha256: ")


def test_yaml_syntax_error_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    path.write_text("documents: [unclosed\n", encoding="utf-8")

    with pytest.raises(ConfigError) as error_info:
        load_snapshot(path, "c1")

    assert error_info.value.source == str(path)
    assert "YAML" in str(error_info.value)


def test_missing_file_error_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.yaml"

    with pytest.raises(ConfigError) as error_info:
        load_snapshot(path, "c1")

    assert error_info.value.source == str(path)
