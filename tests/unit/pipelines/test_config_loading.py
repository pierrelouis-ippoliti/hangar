from pathlib import Path

import pytest
import yaml

from hangar.core.config import config_hash
from hangar.core.errors import ConfigError
from hangar.pipelines.config import load_pipeline_config

V0_CONFIG = Path(__file__).resolve().parents[3] / "configs" / "pipelines" / "v0.yaml"


def test_v0_config_loads_with_the_v0_choices() -> None:
    config = load_pipeline_config(V0_CONFIG)

    assert config.corpus.snapshot == "c1"
    assert config.parsing.pdf.type == "pypdfium2"
    assert config.parsing.car.subparts == ("571", "573")
    assert (config.chunking.size, config.chunking.overlap) == (512, 0)
    assert config.embedding.model == "BAAI/bge-m3"
    assert config.embedding.output == "dense"
    assert config.retrieval.top_k == 5
    assert config.generation.temperature == 0
    assert config.generation.max_output_tokens == 512
    assert config.generation.prompt == "answer-v0"


def test_invalid_value_error_names_the_file_and_the_field(tmp_path: Path) -> None:
    data = yaml.safe_load(V0_CONFIG.read_text(encoding="utf-8"))
    data["chunking"]["size"] = "large"
    path = tmp_path / "broken.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(ConfigError) as error_info:
        load_pipeline_config(path)

    assert str(error_info.value).startswith(f"{path}: chunking.size: ")


def test_yaml_syntax_error_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("corpus: [unclosed\n", encoding="utf-8")

    with pytest.raises(ConfigError) as error_info:
        load_pipeline_config(path)

    assert error_info.value.source == str(path)
    assert "YAML" in str(error_info.value)


def test_missing_file_error_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.yaml"

    with pytest.raises(ConfigError) as error_info:
        load_pipeline_config(path)

    assert error_info.value.source == str(path)


def test_comments_and_layout_do_not_change_the_hash(tmp_path: Path) -> None:
    data = yaml.safe_load(V0_CONFIG.read_text(encoding="utf-8"))
    rewritten = tmp_path / "rewritten.yaml"
    rewritten.write_text(
        "# The v0 values, with no comments and the keys sorted.\n"
        + yaml.safe_dump(data, sort_keys=True, default_flow_style=True),
        encoding="utf-8",
    )

    assert config_hash(load_pipeline_config(rewritten)) == config_hash(
        load_pipeline_config(V0_CONFIG)
    )
