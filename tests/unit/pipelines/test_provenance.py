import re
import subprocess
from pathlib import Path

import pytest

from hangar.core.provenance import CodeVersion
from hangar.pipelines.provenance import code_version, describe_code_version


def git(directory: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(directory), *args],
        check=True,
        capture_output=True,
        text=True,
    )

    return result.stdout.strip()


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """A git checkout with one committed file and no changes."""
    git(tmp_path, "init", "-q")
    (tmp_path / "file.txt").write_text("one")
    git(tmp_path, "add", "file.txt")
    git(
        tmp_path,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.org",
        "commit",
        "-qm",
        "x",
    )

    return tmp_path


def test_a_clean_checkout_gives_its_commit(checkout: Path) -> None:
    assert code_version(checkout) == CodeVersion(
        commit=git(checkout, "rev-parse", "HEAD"), dirty=False
    )


def test_changed_files_make_the_checkout_dirty(checkout: Path) -> None:
    (checkout / "file.txt").write_text("two")

    version = code_version(checkout)

    assert version is not None
    assert version.dirty


def test_untracked_files_make_the_checkout_dirty(checkout: Path) -> None:
    (checkout / "new.txt").write_text("new")

    version = code_version(checkout)

    assert version is not None
    assert version.dirty


def test_a_folder_outside_git_has_no_code_version(tmp_path: Path) -> None:
    assert code_version(tmp_path) is None


def test_the_log_sentence_gives_the_commit_and_state(checkout: Path) -> None:
    (checkout / "file.txt").write_text("two")

    assert re.fullmatch(r"commit [0-9a-f]{40}, dirty", describe_code_version(checkout))


def test_the_log_sentence_says_when_the_commit_is_unknown(tmp_path: Path) -> None:
    assert describe_code_version(tmp_path) == "unknown commit: not a git checkout"
