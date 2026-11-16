"""
File helpers that more than one stage needs: YAML, hashes and outputs.

``core`` does no I/O, so the stages and ``pipelines`` read their YAML files
through this module, then hand the content to ``core`` to validate. The
pipelines also write their outputs through it, so every stage replaces its
output folder the same way.
"""

import hashlib
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
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


def write_text(path: Path, text: str) -> None:
    """
    Write a UTF-8 text file, creating its folders, with a final newline.

    Args:
        path: The file to write. An existing file is overwritten.
        text: The content, without the final newline.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


@contextmanager
def replace_folder(folder: Path) -> Iterator[Path]:
    """
    Replace a folder whole with what the block writes.

    The block writes into an empty folder next to the target, named
    ``<folder>.partial``. When the block finishes, that folder takes the
    target's place. When it raises, the target is left as it was, so an
    output folder never mixes two runs or holds half a run.

    Args:
        folder: The folder to replace. It doesn't need to exist yet.

    Yields:
        The empty folder to write into.
    """
    partial = folder.with_name(f"{folder.name}.partial")
    # A crash in an earlier run can leave this folder behind.
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir(parents=True)

    try:
        yield partial
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise

    shutil.rmtree(folder, ignore_errors=True)
    partial.rename(folder)
