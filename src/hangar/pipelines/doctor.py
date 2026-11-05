"""
The checks behind ``hangar doctor``: is this machine ready to run Hangar?

Each check returns a result instead of raising, so that one failure doesn't
hide the others.
"""

import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from pydantic import SecretStr

from hangar.core.config import PipelineConfig
from hangar.pipelines.settings import Settings

MINIMUM_PYTHON = (3, 12)

# The C1 downloads take about 0.4 GB, and the parsed texts, chunks and
# vectors take less. 2 GB leaves room for them and the logs.
MINIMUM_FREE_BYTES = 2 * 10**9

QDRANT_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True)
class CheckResult:
    """
    The outcome of one check.

    Attributes:
        name: What was checked, such as ``Qdrant``.
        passed: Whether the check passed.
        detail: What was found, and what to do when the check failed.
    """

    name: str
    passed: bool
    detail: str


def run_checks(settings: Settings, config: PipelineConfig) -> list[CheckResult]:
    """
    Run every check, in the order they are reported.

    Args:
        settings: Where Hangar runs.
        config: The pipeline configuration, which names the embedding model.

    Returns:
        One result per check: Python, Qdrant, API key, disk space and model
        cache.
    """
    return [
        check_python(sys.version_info[:3]),
        check_qdrant(str(settings.qdrant_url)),
        check_api_key(settings.mistral_api_key),
        check_disk_space(settings.data_dir),
        check_model_cache(
            settings.hf_home, config.embedding.model, config.embedding.revision
        ),
    ]


def check_python(version: tuple[int, ...]) -> CheckResult:
    """
    Check that Python is recent enough.

    Args:
        version: The running version, such as ``(3, 12, 8)``.

    Returns:
        A pass from Python 3.12 on.
    """
    shown = ".".join(str(part) for part in version)
    if version >= MINIMUM_PYTHON:
        return CheckResult("Python", True, shown)
    return CheckResult("Python", False, f"{shown}, but Hangar needs 3.12 or later")


def check_qdrant(url: str) -> CheckResult:
    """
    Check that Qdrant answers and is ready.

    Args:
        url: The Qdrant server, such as ``http://127.0.0.1:6333/``.

    Returns:
        A pass when the server's ``/readyz`` endpoint answers 200. The
        result shows the URL without any user name or password in it.
    """
    ready_url = url.rstrip("/") + "/readyz"
    shown = _without_credentials(url)
    try:
        with urllib.request.urlopen(ready_url, timeout=QDRANT_TIMEOUT_SECONDS):
            pass
    except urllib.error.HTTPError as error:
        return CheckResult(
            "Qdrant", False, f"{shown.rstrip('/')}/readyz answered {error.code}"
        )
    except OSError as error:
        reason = getattr(error, "reason", error)
        return CheckResult(
            "Qdrant",
            False,
            f"no answer from {shown} ({reason}). Start it with `make qdrant-up`.",
        )
    return CheckResult("Qdrant", True, f"ready at {shown}")


def check_api_key(key: SecretStr | None) -> CheckResult:
    """
    Check that the Mistral API key is set, without calling the API.

    Args:
        key: The key from the settings.

    Returns:
        A pass when the key is set and not empty. The result never shows
        the key.
    """
    if key is None or not key.get_secret_value():
        return CheckResult(
            "API key", False, "MISTRAL_API_KEY is not set. Add it to .env."
        )
    return CheckResult("API key", True, "MISTRAL_API_KEY is set")


def check_disk_space(
    folder: Path, minimum_bytes: int = MINIMUM_FREE_BYTES
) -> CheckResult:
    """
    Check that the data folder's disk has enough free space.

    Args:
        folder: The data folder. It doesn't need to exist yet; the space is
            measured on its nearest existing parent.
        minimum_bytes: The free space needed.

    Returns:
        A pass when at least ``minimum_bytes`` are free.
    """
    free = shutil.disk_usage(_nearest_existing(folder)).free
    found = f"{_gigabytes(free)} free for {folder}"
    if free >= minimum_bytes:
        return CheckResult("Disk space", True, found)
    return CheckResult(
        "Disk space", False, f"{found}, but {_gigabytes(minimum_bytes)} are needed"
    )


def check_model_cache(hf_home: Path | None, model: str, revision: str) -> CheckResult:
    """
    Check that the embedding model is in the Hugging Face cache, or can go there.

    Args:
        hf_home: The Hugging Face folder, or None for the library's default.
        model: The Hugging Face model ID, such as ``BAAI/bge-m3``.
        revision: The pinned commit hash of the model.

    Returns:
        A pass when the pinned revision is already downloaded, or when the
        cache folder can be written so the embed stage can download it.
    """
    hub = (hf_home or _default_hf_home()) / "hub"
    pinned = f"{model} at {revision[:7]}"
    snapshot = hub / f"models--{model.replace('/', '--')}" / "snapshots" / revision
    if snapshot.is_dir():
        return CheckResult("Model cache", True, f"{pinned} is in {hub}")
    writable = _nearest_existing(hub)
    if writable.is_dir() and os.access(writable, os.W_OK):
        return CheckResult(
            "Model cache",
            True,
            f"{pinned} is not downloaded yet; the embed stage will download it"
            f" into {hub}",
        )
    return CheckResult(
        "Model cache", False, f"can't write to {hub}, where {pinned} would go"
    )


def _without_credentials(url: str) -> str:
    # Drop "user:password@" from the address, keeping the host and port.
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        parts._replace(netloc=parts.netloc.rpartition("@")[2])
    )


def _default_hf_home() -> Path:
    # The default that huggingface_hub uses when HF_HOME is not set.
    cache = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(cache) / "huggingface"


def _nearest_existing(path: Path) -> Path:
    path = path.absolute()
    while not path.exists():
        path = path.parent
    return path


def _gigabytes(size: int) -> str:
    return f"{size / 10**9:.1f} GB"
