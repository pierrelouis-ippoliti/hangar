"""
Which code a run used: the git commit and whether the checkout had changes.

The build stages only log it: a report written before its own commit would
otherwise always say dirty. The run record of an answering run keeps it as
fields.
"""

import subprocess
from pathlib import Path

from hangar.core.provenance import CodeVersion


def code_version(directory: Path) -> CodeVersion | None:
    """
    Find the git commit of a checkout and whether it has changes.

    Args:
        directory: A folder inside the checkout.

    Returns:
        The commit and the dirty flag, which is true when files are changed
        or untracked, or None when git or the checkout is missing.
    """
    commit = _git(directory, "rev-parse", "HEAD")
    status = _git(directory, "status", "--porcelain")

    if commit is None or status is None:
        return None

    return CodeVersion(commit=commit, dirty=bool(status))


def describe_code_version(directory: Path) -> str:
    """
    Describe the code version of a checkout in a sentence, for the log.

    Args:
        directory: A folder inside the checkout.

    Returns:
        ``commit <hash>, clean`` or ``commit <hash>, dirty``, or
        ``unknown commit: not a git checkout`` when git or the checkout is
        missing.
    """
    version = code_version(directory)

    if version is None:
        return "unknown commit: not a git checkout"

    return f"commit {version.commit}, {'dirty' if version.dirty else 'clean'}"


def _git(directory: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    return result.stdout.strip() if result.returncode == 0 else None
