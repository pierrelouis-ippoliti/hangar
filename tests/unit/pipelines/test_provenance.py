import re
import subprocess
from pathlib import Path

from hangar.pipelines.provenance import code_version


def git(directory: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(directory), *args], check=True, capture_output=True
    )


def test_a_clean_checkout_gives_its_commit(tmp_path: Path) -> None:
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

    assert re.fullmatch(r"commit [0-9a-f]{40}, clean", code_version(tmp_path))


def test_changed_files_make_the_checkout_dirty(tmp_path: Path) -> None:
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
    (tmp_path / "file.txt").write_text("two")

    assert code_version(tmp_path).endswith(", dirty")


def test_a_folder_outside_git_has_an_unknown_commit(tmp_path: Path) -> None:
    assert code_version(tmp_path) == "unknown commit: not a git checkout"
