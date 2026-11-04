"""Reading the corpus manifest from disk."""

from pathlib import Path

import yaml

from hangar.core.corpus import DocumentSpec, parse_manifest
from hangar.core.errors import ConfigError, FieldProblem


def load_snapshot(path: Path, snapshot: str) -> tuple[DocumentSpec, ...]:
    """
    Read the manifest and return the documents of a snapshot.

    Cancelled documents stay in the manifest as a record but are left out
    of the snapshot.

    Args:
        path: The manifest file, such as ``corpus/manifest.yaml``.
        snapshot: The snapshot the pipeline asks for, such as ``c1``. The
            manifest must be marked with the same snapshot.

    Returns:
        The active documents, in the order the manifest lists them.

    Raises:
        ConfigError: If the file can't be read, isn't valid YAML, holds an
            invalid manifest, or is marked with another snapshot. The error
            names the file, and the field when there is one.
    """
    source = str(path)
    manifest = parse_manifest(_read_yaml(path), source)
    if manifest.snapshot != snapshot:
        raise ConfigError(
            source,
            [
                FieldProblem(
                    "snapshot",
                    f"the manifest is marked {manifest.snapshot!r}, "
                    f"but the pipeline asks for {snapshot!r}",
                )
            ],
        )
    return manifest.active_documents()


def _read_yaml(path: Path) -> object:
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
