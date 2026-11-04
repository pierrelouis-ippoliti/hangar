from pathlib import Path

import pytest

from hangar.core.errors import ConfigError
from hangar.pipelines.settings import load_settings

ENV_EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"
SETTING_NAMES = [
    "MISTRAL_API_KEY",
    "HANGAR_DATA_DIR",
    "HANGAR_QDRANT_URL",
    "HF_HOME",
    "HANGAR_DEVICE",
    "HANGAR_LOG_LEVEL",
]
FAKE_KEY = "fake-key-for-tests"


@pytest.fixture(autouse=True)
def empty_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in SETTING_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_defaults_apply_when_nothing_is_set() -> None:
    settings = load_settings(env_file=None)

    assert settings.mistral_api_key is None
    assert settings.data_dir == Path("data")
    assert str(settings.qdrant_url) == "http://127.0.0.1:6333/"
    assert settings.hf_home is None
    assert settings.device == "cpu"
    assert settings.log_level == "INFO"


def test_example_env_file_loads_and_its_empty_values_keep_the_defaults() -> None:
    assert load_settings(env_file=ENV_EXAMPLE) == load_settings(env_file=None)


def test_values_come_from_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", FAKE_KEY)
    monkeypatch.setenv("HANGAR_DATA_DIR", "/srv/hangar")
    monkeypatch.setenv("HANGAR_QDRANT_URL", "http://qdrant:6333")
    monkeypatch.setenv("HF_HOME", "/srv/models")
    monkeypatch.setenv("HANGAR_DEVICE", "cuda")
    monkeypatch.setenv("HANGAR_LOG_LEVEL", "DEBUG")

    settings = load_settings(env_file=None)

    assert settings.mistral_api_key is not None
    assert settings.mistral_api_key.get_secret_value() == FAKE_KEY
    assert settings.data_dir == Path("/srv/hangar")
    assert str(settings.qdrant_url) == "http://qdrant:6333/"
    assert settings.hf_home == Path("/srv/models")
    assert settings.device == "cuda"
    assert settings.log_level == "DEBUG"


def test_values_come_from_the_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("HANGAR_DEVICE=mps\nHANGAR_LOG_LEVEL=WARNING\n")

    settings = load_settings(env_file=env_file)

    assert (settings.device, settings.log_level) == ("mps", "WARNING")


def test_environment_variables_win_over_the_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("HANGAR_DEVICE=mps\n")
    monkeypatch.setenv("HANGAR_DEVICE", "cuda")

    assert load_settings(env_file=env_file).device == "cuda"


def test_missing_env_file_is_not_an_error(tmp_path: Path) -> None:
    assert load_settings(env_file=tmp_path / ".env").device == "cpu"


def test_api_key_never_appears_in_the_settings_repr_or_str(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", FAKE_KEY)

    settings = load_settings(env_file=None)

    assert FAKE_KEY not in repr(settings)
    assert FAKE_KEY not in str(settings)


def test_invalid_value_error_names_the_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HANGAR_DEVICE", "tpu")

    with pytest.raises(ConfigError) as error_info:
        load_settings(env_file=None)

    assert [p.field for p in error_info.value.problems] == ["HANGAR_DEVICE"]


def test_unknown_name_in_the_env_file_is_rejected_so_typos_are_caught(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("HANGAR_DATADIR=/srv/hangar\n")

    with pytest.raises(ConfigError) as error_info:
        load_settings(env_file=env_file)

    assert error_info.value.source.startswith(str(env_file))
    assert [p.field for p in error_info.value.problems] == ["HANGAR_DATADIR"]
