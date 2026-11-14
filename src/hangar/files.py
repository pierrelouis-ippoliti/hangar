"""
Reading files that more than one stage needs: YAML files and file hashes.

``core`` does no I/O, so the stages and ``pipelines`` read their YAML files
through this module, then hand the content to ``core`` to validate.
"""

import hashlib
from pathlib import Path

import yaml

from hangar.core.errors import ConfigError, FieldProblem

# Hash files 1 MiB at a time, so a large PDF never sits in memory.
HASH_CHUNK_BYTES = 1024 * 1024


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


def file_sha256(path: Path) -> str:
    """
    Compute a file's SHA-256 without reading it all into memory.

    Args:
        path: The file.

    Returns:
        The SHA-256, as 64 lowercase hex characters.
    """
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(HASH_CHUNK_BYTES):
            digest.update(chunk)

    return digest.hexdigest()
