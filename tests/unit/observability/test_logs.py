import io
import json
import logging
import re
from pathlib import Path
from typing import Any

from hangar.observability.logs import (
    configure_logging,
    log_context,
    new_run_id,
)

logger = logging.getLogger("hangar.tests")


def read_json_lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_file_gets_one_json_line_per_record_with_run_id_stage_and_document(
    tmp_path: Path,
) -> None:
    log_file = tmp_path / "logs" / "run.jsonl"
    configure_logging("INFO", log_file, console=io.StringIO())

    with log_context(run_id="20261105T120000Z-abc123", stage="parse"):
        logger.info("started")
        with log_context(document_id="faa-h-8083-31b"):
            logger.info("read %d pages", 42)

    first, second = read_json_lines(log_file)
    assert first["run_id"] == second["run_id"] == "20261105T120000Z-abc123"
    assert first["stage"] == second["stage"] == "parse"
    assert first["document_id"] is None
    assert second["document_id"] == "faa-h-8083-31b"
    assert second["message"] == "read 42 pages"
    assert second["level"] == "INFO"
    assert second["logger"] == "hangar.tests"


def test_screen_gets_a_readable_line_with_stage_and_document(tmp_path: Path) -> None:
    console = io.StringIO()
    configure_logging("INFO", tmp_path / "run.jsonl", console=console)

    with log_context(run_id="r1", stage="parse", document_id="faa-h-8083-31b"):
        logger.warning("page 3 has no text")

    line = console.getvalue()
    assert re.fullmatch(
        r"\d\d:\d\d:\d\d WARNING parse faa-h-8083-31b page 3 has no text\n", line
    )


def test_context_ends_with_its_block(tmp_path: Path) -> None:
    log_file = tmp_path / "run.jsonl"
    configure_logging("INFO", log_file, console=io.StringIO())

    with log_context(run_id="r1", stage="fetch"):
        pass
    logger.info("after")

    (record,) = read_json_lines(log_file)
    assert (record["run_id"], record["stage"]) == (None, None)


def test_records_below_the_level_are_left_out(tmp_path: Path) -> None:
    log_file = tmp_path / "run.jsonl"
    configure_logging("WARNING", log_file, console=io.StringIO())

    logger.info("hidden")
    logger.warning("shown")

    assert [r["message"] for r in read_json_lines(log_file)] == ["shown"]


def test_exception_is_written_with_its_traceback(tmp_path: Path) -> None:
    log_file, console = tmp_path / "run.jsonl", io.StringIO()
    configure_logging("INFO", log_file, console=console)

    try:
        raise ValueError("bad page")
    except ValueError:
        logger.exception("parse failed")

    (record,) = read_json_lines(log_file)
    assert record["message"] == "parse failed"
    assert "ValueError: bad page" in record["exception"]
    assert "ValueError: bad page" in console.getvalue()


def test_configuring_again_replaces_the_previous_handlers(tmp_path: Path) -> None:
    first_file, second_file = tmp_path / "first.jsonl", tmp_path / "second.jsonl"
    configure_logging("INFO", first_file, console=io.StringIO())
    configure_logging("INFO", second_file, console=io.StringIO())

    logger.info("once")

    assert first_file.read_text() == ""
    assert len(read_json_lines(second_file)) == 1


def test_run_ids_hold_the_start_time_and_differ_between_runs() -> None:
    first, second = new_run_id(), new_run_id()

    assert re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{6}", first)
    assert first != second


FAKE_KEY = "fake-mistral-key-0123456789"


def test_api_key_is_redacted_from_messages_arguments_and_tracebacks(
    tmp_path: Path,
) -> None:
    log_file, console = tmp_path / "run.jsonl", io.StringIO()
    configure_logging("INFO", log_file, console=console, secrets=[FAKE_KEY])

    logger.info(f"key in the message: {FAKE_KEY}")
    logger.info("key in an argument: %s", FAKE_KEY)
    logging.getLogger("some_library").info("header Authorization: Bearer %s", FAKE_KEY)
    try:
        raise RuntimeError(f"request failed with key {FAKE_KEY}")
    except RuntimeError:
        logger.exception("call failed")

    for output in (log_file.read_text(), console.getvalue()):
        assert FAKE_KEY not in output
        assert output.count("[REDACTED]") == 4


def test_empty_secret_redacts_nothing(tmp_path: Path) -> None:
    log_file = tmp_path / "run.jsonl"
    configure_logging("INFO", log_file, console=io.StringIO(), secrets=[""])

    logger.info("nothing to hide")

    (record,) = read_json_lines(log_file)
    assert record["message"] == "nothing to hide"
