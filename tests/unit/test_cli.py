import hashlib
import json
import socket
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pytest
import yaml

from hangar.cli import main
from hangar.corpus.download import LocalCopyDownloader

ROOT = Path(__file__).resolve().parents[2]
V0_CONFIG = ROOT / "configs" / "pipelines" / "v0.yaml"
SETTING_NAMES = [
    "MISTRAL_API_KEY",
    "HANGAR_DATA_DIR",
    "HANGAR_QDRANT_URL",
    "HF_HOME",
    "HANGAR_DEVICE",
    "HANGAR_LOG_LEVEL",
]
FAKE_KEY = "fake-mistral-key-0123456789"
STAGE_COMMANDS = [
    ["parse"],
    ["chunk"],
    ["embed"],
    ["index"],
    ["search"],
    ["ask"],
    ["seed", "run"],
    ["seed", "summarize"],
]


@pytest.fixture(autouse=True)
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run in an empty folder, with no .env file and no settings set."""
    for name in SETTING_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run_logs(workspace: Path) -> list[Path]:
    # A run log is named after its run ID, such as 20261105T114319Z-7e7595.
    return list((workspace / "data" / "logs").glob("*T*Z-*.jsonl"))


def log_records(workspace: Path) -> list[dict[str, Any]]:
    (log_file,) = run_logs(workspace)
    return [json.loads(line) for line in log_file.read_text().splitlines()]


def unused_port_url() -> str:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}/"


def test_version_flag_prints_the_installed_package_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"hangar {version('hangar')}\n"


def test_a_command_is_required() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([])

    assert exit_info.value.code == 2


@pytest.mark.parametrize("command", STAGE_COMMANDS, ids=" ".join)
def test_stage_commands_read_the_config_and_say_they_are_not_built_yet(
    command: list[str], workspace: Path
) -> None:
    assert main([*command, "--config", str(V0_CONFIG)]) == 1

    records = log_records(workspace)
    assert {r["stage"] for r in records} == {" ".join(command)}
    assert len({r["run_id"] for r in records}) == 1
    assert any("config hash" in r["message"] for r in records)
    assert "is not built yet" in records[-1]["message"]


def test_config_defaults_to_the_v0_pipeline(workspace: Path) -> None:
    (workspace / "configs" / "pipelines").mkdir(parents=True)
    (workspace / "configs" / "pipelines" / "v0.yaml").write_text(V0_CONFIG.read_text())

    main(["parse"])

    assert any(
        r["message"].startswith("read configs/pipelines/v0.yaml")
        for r in log_records(workspace)
    )


def test_invalid_config_is_reported_with_its_file(workspace: Path) -> None:
    config = workspace / "broken.yaml"
    config.write_text("corpus: {}\n")

    assert main(["doctor", "--config", str(config)]) == 1

    assert any(
        r["level"] == "ERROR" and r["message"].startswith(str(config))
        for r in log_records(workspace)
    )


def test_invalid_settings_are_reported_before_logging_starts(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("HANGAR_DEVICE", "tpu")

    assert main(["doctor", "--config", str(V0_CONFIG)]) == 1

    assert "HANGAR_DEVICE" in capsys.readouterr().err


def test_doctor_passes_when_every_check_passes(
    fake_qdrant: Any,
    monkeypatch: pytest.MonkeyPatch,
    workspace: Path,
) -> None:
    monkeypatch.setenv("HANGAR_QDRANT_URL", fake_qdrant.url)
    monkeypatch.setenv("MISTRAL_API_KEY", FAKE_KEY)

    assert main(["doctor", "--config", str(V0_CONFIG)]) == 0

    messages = [r["message"] for r in log_records(workspace)]
    for check in ("Python", "Qdrant", "API key", "Disk space", "Model cache"):
        assert any(m.startswith(f"pass  {check}:") for m in messages), check


def test_doctor_reports_every_check_and_fails_when_one_fails(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("HANGAR_QDRANT_URL", unused_port_url())
    monkeypatch.setenv("MISTRAL_API_KEY", FAKE_KEY)

    assert main(["doctor", "--config", str(V0_CONFIG)]) == 1

    screen = capsys.readouterr().err
    assert "fail  Qdrant:" in screen
    for check in ("Python", "API key", "Disk space", "Model cache"):
        assert f"pass  {check}:" in screen
    assert "1 of 5 checks failed: Qdrant" in screen


def test_api_key_never_reaches_the_screen_or_the_log_file(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", FAKE_KEY)
    monkeypatch.setenv("HANGAR_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("HANGAR_QDRANT_URL", unused_port_url())

    main(["doctor", "--config", str(V0_CONFIG)])

    (log_file,) = run_logs(workspace)
    assert FAKE_KEY not in log_file.read_text()
    assert FAKE_KEY not in capsys.readouterr().err


def test_unexpected_error_is_logged_with_its_traceback_and_the_key_redacted(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def broken_checks(*args: object) -> None:
        raise RuntimeError(f"request failed with key {FAKE_KEY}")

    monkeypatch.setattr("hangar.pipelines.commands.run_checks", broken_checks)
    monkeypatch.setenv("MISTRAL_API_KEY", FAKE_KEY)

    assert main(["doctor", "--config", str(V0_CONFIG)]) == 1

    (last,) = log_records(workspace)[-1:]
    assert last["message"] == "hangar doctor stopped on an unexpected error"
    assert "RuntimeError: request failed with key [REDACTED]" in last["exception"]
    assert FAKE_KEY not in capsys.readouterr().err


def write_corpus(
    workspace: Path, monkeypatch: pytest.MonkeyPatch, *, wrong_hash_for: str = ""
) -> tuple[Path, LocalCopyDownloader]:
    """Write a two-document manifest and a config that uses it; serve the files."""
    sources = workspace / "sources"
    sources.mkdir()
    documents, files = [], {}

    for document_id, content in [("doc-one", b"one"), ("doc-two", b"two")]:
        (sources / document_id).write_bytes(content)
        url = f"https://example.org/{document_id}.pdf"
        files[url] = sources / document_id
        sha256 = hashlib.sha256(content).hexdigest()
        documents.append(
            {
                "id": document_id,
                "title": "Example",
                "authority": "FAA",
                "type": "handbook",
                "language": "en",
                "source_url": url,
                "official_url": url,
                "format": "pdf",
                "edition": "B",
                "content_date": "2023-01-01",
                "page_modified_date": "2023-01-01",
                "retrieved_on": "2026-11-04",
                "status": "active",
                "sha256": "f" * 64 if document_id == wrong_hash_for else sha256,
                "reuse_note": "Made up for tests.",
            }
        )

    manifest = workspace / "manifest.yaml"
    manifest.write_text(yaml.safe_dump({"snapshot": "c1", "documents": documents}))
    config = yaml.safe_load(V0_CONFIG.read_text())
    config["corpus"]["manifest"] = str(manifest)
    config_path = workspace / "pipeline.yaml"
    config_path.write_text(yaml.safe_dump(config))

    downloader = LocalCopyDownloader(files)
    monkeypatch.setattr(
        "hangar.pipelines.fetch.HttpDownloader", lambda user_agent: downloader
    )

    return config_path, downloader


def test_fetch_downloads_every_document_then_nothing_on_a_second_run(
    monkeypatch: pytest.MonkeyPatch, workspace: Path
) -> None:
    config, downloader = write_corpus(workspace, monkeypatch)

    assert main(["fetch", "--config", str(config)]) == 0
    assert sorted(p.name for p in (workspace / "data" / "raw").iterdir()) == [
        "doc-one.pdf",
        "doc-two.pdf",
    ]
    assert (workspace / "data" / "logs" / "fetch-log.jsonl").is_file()
    assert {r["document_id"] for r in log_records(workspace)} >= {"doc-one", "doc-two"}

    downloader.downloaded.clear()
    for log_file in run_logs(workspace):
        log_file.unlink()

    assert main(["fetch", "--config", str(config)]) == 0
    assert downloader.downloaded == []
    assert any(
        "0 downloaded, 2 already present" in r["message"]
        for r in log_records(workspace)
    )


def test_fetch_stops_on_a_hash_mismatch_with_an_error_naming_the_document(
    monkeypatch: pytest.MonkeyPatch, workspace: Path
) -> None:
    config, _ = write_corpus(workspace, monkeypatch, wrong_hash_for="doc-two")

    assert main(["fetch", "--config", str(config)]) == 1

    last = log_records(workspace)[-1]
    assert last["level"] == "ERROR"
    assert last["message"].startswith("doc-two: ")
    assert "SHA-256" in last["message"]
