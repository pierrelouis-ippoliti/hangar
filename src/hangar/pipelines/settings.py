"""
Environment settings: where things run.

Settings come from environment variables and an optional ``.env`` file, and
never change a run's results, so they stay out of the configuration hash.
``.env.example`` lists every name.
"""

from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from hangar.core.errors import ConfigError, field_problems


class Settings(BaseSettings):
    """
    Where Hangar runs: folders, services, device and secrets.

    Each field is read from the environment variable named in its alias.
    An empty value, as in ``.env.example``, counts as unset and keeps the
    default. Unknown names in the ``.env`` file are rejected, so a typo
    can't silently leave a setting at its default.

    Attributes:
        mistral_api_key: The Mistral API key (``MISTRAL_API_KEY``). It
            shows as ``**********`` when the settings are printed.
        data_dir: The folder for downloads and pipeline outputs
            (``HANGAR_DATA_DIR``).
        qdrant_url: The Qdrant server (``HANGAR_QDRANT_URL``).
        hf_home: The Hugging Face cache folder (``HF_HOME``), or None for
            the library's default.
        device: Where the embedding model runs (``HANGAR_DEVICE``).
        log_level: The lowest level of log message shown
            (``HANGAR_LOG_LEVEL``).
    """

    model_config = SettingsConfigDict(
        frozen=True, env_ignore_empty=True, case_sensitive=True
    )

    mistral_api_key: SecretStr | None = Field(
        default=None, validation_alias="MISTRAL_API_KEY"
    )
    data_dir: Path = Field(default=Path("data"), validation_alias="HANGAR_DATA_DIR")
    qdrant_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://127.0.0.1:6333"),
        validation_alias="HANGAR_QDRANT_URL",
    )
    hf_home: Path | None = Field(default=None, validation_alias="HF_HOME")
    device: Literal["cpu", "cuda", "mps"] = Field(
        default="cpu", validation_alias="HANGAR_DEVICE"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", validation_alias="HANGAR_LOG_LEVEL"
    )


def load_settings(env_file: Path | None = Path(".env")) -> Settings:
    """
    Read the settings from the environment and an optional ``.env`` file.

    Environment variables win over the file. A missing file is not an
    error.

    Args:
        env_file: The ``.env`` file to read, or None to read only the
            environment.

    Returns:
        The validated settings.

    Raises:
        ConfigError: If a value is invalid or the file holds an unknown
            name. The error names the variable.
    """
    source = "the environment" if env_file is None else f"{env_file} or the environment"
    try:
        return Settings(_env_file=env_file)
    except ValidationError as error:
        raise ConfigError(source, field_problems(error)) from error
