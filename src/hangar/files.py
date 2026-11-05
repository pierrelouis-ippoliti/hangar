"""
Reading the files that Hangar is configured with.

``core`` does no I/O, so the stages and ``pipelines`` read their YAML files
through this module, then hand the content to ``core`` to validate.
"""

from pathlib import Path

import yaml

from hangar.core.errors import ConfigError, FieldProblem


def read_yaml(path: Path) -> object:
    """
    Read a YAML file.

    Args:
        path: The file to read.

    Returns:
        The file's content as Python values, or None if the file is empty.

    Raises:
        ConfigError: If the file can't be read or isn't valid YAML. The
            error names the file.
    """
    source = str(path)

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(
            source, [FieldProblem(None, f"can't read the file: {error.strerror}")]
        ) from error

    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigError(
            source, [FieldProblem(None, f"invalid YAML: {error}")]
        ) from error
