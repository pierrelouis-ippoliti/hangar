"""
What each ``hangar`` subcommand runs, with its logging and its errors.

``cli`` turns the command line into a command name and a configuration path;
everything after that happens here, so ``cli`` imports nothing but this
package.
"""

import logging
import sys
from pathlib import Path

from hangar.core.config import PipelineConfig, config_hash
from hangar.core.errors import ConfigError, HangarError
from hangar.observability.logs import (
    close_logging,
    configure_logging,
    log_context,
    new_run_id,
)
from hangar.pipelines.config import load_pipeline_config
from hangar.pipelines.doctor import run_checks
from hangar.pipelines.fetch import run_fetch
from hangar.pipelines.settings import Settings, load_settings

logger = logging.getLogger(__name__)


def run_command(command: str, config_path: Path) -> int:
    """
    Run one ``hangar`` subcommand as a logged run.

    Reads the settings, starts a run with its own ID and log file
    (``<data folder>/logs/<run ID>.jsonl``), reads the pipeline file, then
    runs the command. Errors are logged rather than raised, so they go
    through the same redaction as every other record.

    Args:
        command: The subcommand, such as ``doctor`` or ``seed run``.
        config_path: The pipeline file to read.

    Returns:
        The exit code: 0 on success, 1 on failure.
    """
    try:
        settings = load_settings()
    except ConfigError as error:
        # Logging needs the settings, so this one goes straight to the screen.
        print(f"hangar: {error}", file=sys.stderr)
        return 1

    run_id = new_run_id()
    log_file = settings.data_dir / "logs" / f"{run_id}.jsonl"
    key = settings.mistral_api_key

    configure_logging(
        settings.log_level,
        log_file,
        secrets=[key.get_secret_value()] if key else [],
    )

    with log_context(run_id=run_id, stage=command):
        try:
            logger.info("run ID %s, logging to %s", run_id, log_file)
            config = load_pipeline_config(config_path)
            logger.info("read %s, config hash %s", config_path, config_hash(config))

            return _run(command, settings, config)
        except HangarError as error:
            logger.error("%s", error)
            return 1
        except Exception:
            logger.exception("hangar %s stopped on an unexpected error", command)
            return 1
        finally:
            close_logging()


def _run(command: str, settings: Settings, config: PipelineConfig) -> int:
    if command == "doctor":
        return _doctor(settings, config)

    if command == "fetch":
        run_fetch(settings, config)

        return 0

    logger.error("hangar %s is not built yet", command)

    return 1


def _doctor(settings: Settings, config: PipelineConfig) -> int:
    results = run_checks(settings, config)

    for result in results:
        if result.passed:
            logger.info("pass  %s: %s", result.name, result.detail)
        else:
            logger.error("fail  %s: %s", result.name, result.detail)

    failed = [result.name for result in results if not result.passed]

    if failed:
        logger.error(
            "%d of %d checks failed: %s", len(failed), len(results), ", ".join(failed)
        )
        return 1

    logger.info("all %d checks passed", len(results))

    return 0
