"""
Which code a run used, for its log.

The commit and the dirty flag go in the run's log, not in the committed
results: a report written before its own commit would otherwise always say
dirty.
"""

import subprocess
from pathlib import Path


def code_version(directory: Path) -> str:
    """
    Describe the git commit of a checkout and whether it has changes.

    Args:
        directory: A folder inside the checkout.

    Returns:
        ``commit <hash>, clean`` or ``commit <hash>, dirty`` when files are
        changed or untracked, or ``unknown commit: not a git checkout`` when
        git or the checkout is missing.
    """
    commit = _git(directory, "rev-parse", "HEAD")
    status = _git(directory, "status", "--porcelain")

    if commit is None or status is None:
        return "unknown commit: not a git checkout"

    return f"commit {commit}, {'dirty' if status else 'clean'}"


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
