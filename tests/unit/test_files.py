import hashlib
from pathlib import Path

import pytest

from hangar.core.errors import ConfigError
from hangar.files import file_sha256, read_yaml, replace_folder, write_text


def test_yaml_content_is_returned_as_python_values(tmp_path: Path) -> None:
    path = tmp_path / "file.yaml"
    path.write_text("snapshot: c1\nsizes: [512, 256]\n", encoding="utf-8")

    assert read_yaml(path) == {"snapshot": "c1", "sizes": [512, 256]}


def test_empty_file_gives_none(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")

    assert read_yaml(path) is None


def test_yaml_syntax_error_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("corpus: [unclosed\n", encoding="utf-8")

    with pytest.raises(ConfigError) as error_info:
        read_yaml(path)

    assert error_info.value.source == str(path)
    assert str(error_info.value).startswith(f"{path}: invalid YAML: ")


def test_missing_file_error_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.yaml"

    with pytest.raises(ConfigError) as error_info:
        read_yaml(path)

    assert error_info.value.source == str(path)
    assert str(error_info.value).startswith(f"{path}: can't read the file: ")


def test_file_sha256_matches_hashlib(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_bytes(b"hangar")

    assert file_sha256(path) == hashlib.sha256(b"hangar").hexdigest()


def test_write_text_creates_the_folders_and_ends_with_a_newline(
    tmp_path: Path,
) -> None:
    path = tmp_path / "a" / "b" / "file.json"

    write_text(path, "{}")

    assert path.read_text(encoding="utf-8") == "{}\n"


def test_replace_folder_swaps_in_what_the_block_wrote(tmp_path: Path) -> None:
    folder = tmp_path / "out"
    folder.mkdir()
    (folder / "old.json").write_text("old")

    with replace_folder(folder) as partial:
        (partial / "new.json").write_text("new")

    assert sorted(p.name for p in folder.iterdir()) == ["new.json"]
    assert not (tmp_path / "out.partial").exists()


def test_replace_folder_creates_a_missing_folder(tmp_path: Path) -> None:
    folder = tmp_path / "a" / "out"

    with replace_folder(folder) as partial:
        (partial / "new.json").write_text("new")

    assert (folder / "new.json").read_text() == "new"


def test_an_error_in_the_block_leaves_the_old_folder_whole(tmp_path: Path) -> None:
    folder = tmp_path / "out"
    folder.mkdir()
    (folder / "old.json").write_text("old")

    with pytest.raises(RuntimeError), replace_folder(folder) as partial:
        (partial / "new.json").write_text("new")
        raise RuntimeError("write failed")

    assert sorted(p.name for p in folder.iterdir()) == ["old.json"]
    assert not (tmp_path / "out.partial").exists()


def test_a_partial_folder_left_by_a_crash_is_cleared(tmp_path: Path) -> None:
    leftover = tmp_path / "out.partial"
    leftover.mkdir()
    (leftover / "stale.json").write_text("stale")

    with replace_folder(tmp_path / "out") as partial:
        assert list(partial.iterdir()) == []
