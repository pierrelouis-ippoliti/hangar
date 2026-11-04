"""Reading a pipeline file from disk."""

from pathlib import Path

import yaml

from hangar.core.config import PipelineConfig, parse_pipeline_config
from hangar.core.errors import ConfigError, FieldProblem


def load_pipeline_config(path: Path) -> PipelineConfig:
    """
    Read and validate a pipeline file.

    Args:
        path: The YAML pipeline file, such as ``configs/pipelines/v0.yaml``.

    Returns:
        The validated configuration.

    Raises:
        ConfigError: If the file can't be read, isn't valid YAML, or
            doesn't hold a valid configuration. The error names the file,
            and the field when there is one.
    """
    source = str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(
            source, [FieldProblem(None, f"can't read the file: {error.strerror}")]
        ) from error
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigError(
            source, [FieldProblem(None, f"invalid YAML: {error}")]
        ) from error
    return parse_pipeline_config(data, source)
