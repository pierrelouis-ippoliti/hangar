"""The parse pipeline: from the raw folder to the parsed folder and the report."""

import logging
import shutil
from pathlib import Path

from hangar.core.config import PipelineConfig, config_hash
from hangar.core.corpus import DocumentSpec, raw_artifact_id
from hangar.core.parsed import ParsedDocument, ParsedFile
from hangar.corpus.manifest import load_snapshot
from hangar.observability.logs import log_context
from hangar.parsing.parser import ParseError, Parser
from hangar.parsing.report import (
    ParseCheckError,
    ParseReport,
    check_report,
    document_report,
)
from hangar.pipelines.provenance import code_version
from hangar.pipelines.registry import build_parsers
from hangar.pipelines.settings import Settings

logger = logging.getLogger(__name__)


def run_parse(
    settings: Settings, config: PipelineConfig, results_dir: Path = Path("results")
) -> ParseReport:
    """
    Parse every document of the configured snapshot, then check the results.

    The report is written in every case, so a failed check can be read. The
    parsed files are written only when every check passes, and replace the
    snapshot's folder whole, so it never mixes two runs.

    Args:
        settings: Where Hangar runs. Documents are read from
            ``<data folder>/raw`` and written to
            ``<data folder>/parsed/<snapshot>/<document ID>.json``.
        config: The pipeline configuration: the snapshot, the parser
            settings and the thresholds.
        results_dir: The folder of committed results. The report goes to
            ``<results_dir>/<run name>/parse-report.json``.

    Returns:
        The parse report.

    Raises:
        ConfigError: If the manifest can't be read or is invalid.
        ParseError: If a document's file is missing or can't be parsed.
        ParseCheckError: If a document is outside the thresholds.
    """
    manifest, snapshot = config.corpus.manifest, config.corpus.snapshot
    documents = load_snapshot(manifest, snapshot)
    logger.info(
        "read %s: %d documents in snapshot %s", manifest, len(documents), snapshot
    )
    logger.info("code at %s", code_version(Path.cwd()))

    parsers = build_parsers(config.parsing)
    raw_dir = settings.data_dir / "raw"
    parsed = [
        _parse_document(document, raw_dir, parsers[document.format])
        for document in documents
    ]

    hash_ = config_hash(config)
    report = ParseReport(
        snapshot=snapshot,
        config_hash=hash_,
        documents=tuple(
            document_report(document, result)
            for document, result in zip(documents, parsed, strict=True)
        ),
    )
    report_path = results_dir / config.run.name / "parse-report.json"
    _write_text(report_path, report.model_dump_json(indent=2))
    logger.info("wrote %s", report_path)

    problems = check_report(report, config.parsing.checks)

    if problems:
        raise ParseCheckError(problems)

    parsed_dir = settings.data_dir / "parsed" / snapshot
    files = [ParsedFile(config_hash=hash_, document=p) for p in parsed]
    _replace_folder(parsed_dir, files)
    logger.info("wrote %s: %d documents", parsed_dir, len(parsed))

    return report


def _parse_document(
    document: DocumentSpec, raw_dir: Path, parser: Parser
) -> ParsedDocument:
    with log_context(document_id=document.id):
        path = raw_dir / raw_artifact_id(document)

        if not path.is_file():
            raise ParseError(
                f"{document.id}: {path} is missing; run hangar fetch first"
            )

        parsed = parser.parse(document, path)
        logger.info(
            "parsed %s: %d passages, %d characters, %d warnings",
            path,
            len(parsed.passages),
            len(parsed.text),
            len(parsed.warnings),
        )

        for warning in parsed.warnings:
            logger.warning("%s: %s", warning.code, warning.message)

        return parsed


def _replace_folder(folder: Path, files: list[ParsedFile]) -> None:
    # Write next to the folder first, so a failed write leaves the previous
    # results whole.
    partial = folder.with_name(f"{folder.name}.partial")
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir(parents=True)

    for parsed_file in files:
        path = partial / f"{parsed_file.document.document_id}.json"
        _write_text(path, parsed_file.model_dump_json())

    shutil.rmtree(folder, ignore_errors=True)
    partial.rename(folder)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")
