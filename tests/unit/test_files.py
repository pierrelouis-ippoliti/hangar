from pathlib import Path

import pytest

from hangar.core.errors import ConfigError
from hangar.files import read_yaml


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
