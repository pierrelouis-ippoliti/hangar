import socket
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from hangar.pipelines.doctor import (
    check_api_key,
    check_disk_space,
    check_model_cache,
    check_python,
    check_qdrant,
)

MODEL = "BAAI/bge-m3"
REVISION = "5617a9f61b028005a4858fdac845db406aefb181"


def closed_port_url() -> str:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}/"


def test_python_passes_from_3_12_and_fails_before() -> None:
    assert check_python((3, 12, 0)).passed
    assert check_python((3, 13, 1)).passed

    result = check_python((3, 11, 9))
    assert not result.passed
    assert "3.11.9" in result.detail


def test_qdrant_passes_when_it_says_it_is_ready(fake_qdrant: Any) -> None:
    result = check_qdrant(fake_qdrant.url)

    assert result.passed
    assert fake_qdrant.url in result.detail


def test_qdrant_fails_when_it_is_not_ready(fake_qdrant: Any) -> None:
    fake_qdrant.status = 503

    result = check_qdrant(fake_qdrant.url)

    assert not result.passed
    assert "503" in result.detail


def test_qdrant_fails_with_a_hint_when_nothing_answers() -> None:
    result = check_qdrant(closed_port_url())

    assert not result.passed
    assert "make qdrant-up" in result.detail


def test_api_key_passes_when_set_and_never_shows_the_key() -> None:
    result = check_api_key(SecretStr("fake-key-for-tests"))

    assert result.passed
    assert "fake-key-for-tests" not in result.detail


@pytest.mark.parametrize("key", [None, SecretStr("")])
def test_api_key_fails_when_missing_or_empty(key: SecretStr | None) -> None:
    result = check_api_key(key)

    assert not result.passed
    assert ".env" in result.detail


def test_disk_space_passes_above_the_minimum_and_fails_below(tmp_path: Path) -> None:
    assert check_disk_space(tmp_path, minimum_bytes=0).passed
    assert not check_disk_space(tmp_path, minimum_bytes=10**18).passed


def test_disk_space_measures_the_nearest_existing_folder(tmp_path: Path) -> None:
    assert check_disk_space(tmp_path / "data" / "not-yet", minimum_bytes=0).passed


def test_model_cache_passes_when_the_pinned_revision_is_there(tmp_path: Path) -> None:
    snapshot = tmp_path / "hub" / "models--BAAI--bge-m3" / "snapshots" / REVISION
    snapshot.mkdir(parents=True)

    result = check_model_cache(tmp_path, MODEL, REVISION)

    assert result.passed
    assert "5617a9f" in result.detail
    assert "not downloaded" not in result.detail


def test_model_cache_passes_when_the_model_can_still_be_downloaded(
    tmp_path: Path,
) -> None:
    result = check_model_cache(tmp_path / "hf", MODEL, REVISION)

    assert result.passed
    assert "not downloaded yet" in result.detail


def test_model_cache_fails_when_the_cache_folder_cant_be_created(
    tmp_path: Path,
) -> None:
    blocker = tmp_path / "a-file"
    blocker.write_text("")

    result = check_model_cache(blocker / "hf", MODEL, REVISION)

    assert not result.passed
