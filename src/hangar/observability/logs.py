"""
Structured logs: JSON lines in a file, readable lines on screen.

Code anywhere in Hangar logs with the standard library, through
``logging.getLogger(__name__)``. Each record also carries the run ID, the
stage and the document being worked on, taken from the innermost
``log_context`` block, so the code that logs doesn't pass them along.

Secrets given to ``configure_logging``, such as the Mistral API key, are
replaced by ``[REDACTED]`` before a record is written anywhere, including
in tracebacks and in records from other libraries.
"""

import json
import logging
import sys
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex
from typing import TextIO

# Handlers installed by configure_logging carry this prefix in their name,
# so they can be found and removed without touching anyone else's.
_HANDLER_PREFIX = "hangar."

REDACTED = "[REDACTED]"

_run_id: ContextVar[str | None] = ContextVar("hangar_run_id", default=None)
_stage: ContextVar[str | None] = ContextVar("hangar_stage", default=None)
_document_id: ContextVar[str | None] = ContextVar("hangar_document_id", default=None)


def new_run_id() -> str:
    """
    Create an ID for a new run.

    Returns:
        The start time in UTC followed by six random hex characters, such
        as ``20261105T142233Z-3fa91c``. IDs sort by start time.
    """
    return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{token_hex(3)}"


@contextmanager
def log_context(
    *,
    run_id: str | None = None,
    stage: str | None = None,
    document_id: str | None = None,
) -> Iterator[None]:
    """
    Attach a run ID, stage or document ID to every record logged in a block.

    Blocks can be nested. A value left as None keeps the value of the
    enclosing block, and each value goes back to the enclosing one when
    the block ends.

    Args:
        run_id: The ID of the current run.
        stage: The stage being run, such as ``parse``.
        document_id: The document being worked on, such as
            ``faa-h-8083-31b``.

    Yields:
        Nothing. The values apply until the block ends.
    """
    values = ((_run_id, run_id), (_stage, stage), (_document_id, document_id))
    tokens: list[tuple[ContextVar[str | None], Token[str | None]]] = [
        (variable, variable.set(value))
        for variable, value in values
        if value is not None
    ]
    try:
        yield
    finally:
        for variable, token in reversed(tokens):
            variable.reset(token)


def configure_logging(
    level: str,
    log_file: Path,
    *,
    console: TextIO | None = None,
    secrets: Iterable[str] = (),
) -> None:
    """
    Send log records to a JSON lines file and to the screen.

    Replaces the handlers installed by an earlier call. Records from other
    libraries go to the same places, since the handlers sit on the root
    logger.

    Args:
        level: The lowest level written, such as ``INFO``.
        log_file: The JSON lines file. Its folder is created if needed.
        console: Where the readable lines go. Defaults to standard error.
        secrets: Values that must never be written, such as the API key.
            Empty values are ignored.
    """
    close_logging()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(_JsonLinesFormatter())
    console_handler = logging.StreamHandler(console or sys.stderr)
    console_handler.setFormatter(_ReadableFormatter())

    redactor = _SecretRedactor(secrets)
    root = logging.getLogger()
    for name, handler in (("file", file_handler), ("console", console_handler)):
        handler.set_name(_HANDLER_PREFIX + name)
        # Filters on a handler see every record it receives, including those
        # from child loggers; filters on the root logger would not.
        handler.addFilter(_ContextFilter())
        handler.addFilter(redactor)
        root.addHandler(handler)
    root.setLevel(level)


def close_logging() -> None:
    """Remove and close the handlers installed by ``configure_logging``."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if (handler.get_name() or "").startswith(_HANDLER_PREFIX):
            root.removeHandler(handler)
            handler.close()


class _ContextFilter(logging.Filter):
    """Copy the run ID, stage and document ID of the current block onto a record."""

    def filter(self, record: logging.LogRecord) -> bool:
        for name, variable in (
            ("run_id", _run_id),
            ("stage", _stage),
            ("document_id", _document_id),
        ):
            if not hasattr(record, name):
                setattr(record, name, variable.get())
        return True


class _SecretRedactor(logging.Filter):
    """Replace each secret in a record's message, traceback and stack with REDACTED."""

    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        # Longest first, so that a secret containing another is replaced whole.
        self._secrets = sorted({s for s in secrets if s}, key=len, reverse=True)
        self._formatter = logging.Formatter()

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True
        # Merge the arguments into the message first: a secret is often
        # passed as an argument, as in log.info("key %s", key).
        record.msg = self._redact(record.getMessage())
        record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = self._formatter.formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = self._redact(record.exc_text)
        if record.stack_info:
            record.stack_info = self._redact(record.stack_info)
        return True

    def _redact(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, REDACTED)
        return text


class _JsonLinesFormatter(logging.Formatter):
    """Write a record as one JSON object on one line."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "run_id": getattr(record, "run_id", None),
            "stage": getattr(record, "stage", None),
            "document_id": getattr(record, "document_id", None),
            "message": record.getMessage(),
        }
        details = _exception_and_stack(self, record)
        if details:
            entry["exception"] = details
        return json.dumps(entry, ensure_ascii=False)


class _ReadableFormatter(logging.Formatter):
    """Write a record as ``time level stage document message``, skipping empty parts."""

    def format(self, record: logging.LogRecord) -> str:
        parts = [
            self.formatTime(record, "%H:%M:%S"),
            f"{record.levelname:<7}",
            getattr(record, "stage", None),
            getattr(record, "document_id", None),
            record.getMessage(),
        ]
        line = " ".join(part for part in parts if part)
        details = _exception_and_stack(self, record)
        return f"{line}\n{details}" if details else line


def _exception_and_stack(
    formatter: logging.Formatter, record: logging.LogRecord
) -> str:
    # Like logging.Formatter.format, keep the formatted traceback on the
    # record so that a second handler reuses it.
    if record.exc_info and not record.exc_text:
        record.exc_text = formatter.formatException(record.exc_info)
    return "\n".join(part for part in (record.exc_text, record.stack_info) if part)
