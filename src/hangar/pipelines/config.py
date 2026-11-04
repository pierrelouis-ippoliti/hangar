"""Reading a pipeline file from disk."""

from pathlib import Path

from hangar.core.config import PipelineConfig, parse_pipeline_config
from hangar.files import read_yaml


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
    return parse_pipeline_config(read_yaml(path), str(path))
