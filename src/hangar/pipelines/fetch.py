"""The fetch pipeline: from the manifest to the raw folder."""

import logging
from importlib.metadata import version

from hangar.core.config import PipelineConfig
from hangar.corpus.download import Downloader, HttpDownloader
from hangar.corpus.fetch import FetchSummary, fetch_documents
from hangar.corpus.manifest import load_snapshot
from hangar.pipelines.settings import Settings

# Says who is downloading and where to read about it, without any personal
# contact details.
USER_AGENT = (
    f"hangar/{version('hangar')} (+https://github.com/pierrelouis-ippoliti/hangar)"
)

logger = logging.getLogger(__name__)


def run_fetch(
    settings: Settings, config: PipelineConfig, downloader: Downloader | None = None
) -> FetchSummary:
    """
    Download every document of the configured snapshot into the raw folder.

    Args:
        settings: Where Hangar runs. Files go to ``<data folder>/raw``,
            and the fetch log to ``<data folder>/logs/fetch-log.jsonl``.
        config: The pipeline configuration, which names the manifest and
            the snapshot.
        downloader: What downloads each file. Defaults to an
            ``HttpDownloader``; tests pass a fake.

    Returns:
        Which documents were downloaded and which were already there.

    Raises:
        ConfigError: If the manifest can't be read or is invalid.
        FetchError: If a document can't be downloaded or its hash differs
            from the manifest's.
    """
    manifest, snapshot = config.corpus.manifest, config.corpus.snapshot
    documents = load_snapshot(manifest, snapshot)
    logger.info(
        "read %s: %d documents in snapshot %s", manifest, len(documents), snapshot
    )

    raw_dir = settings.data_dir / "raw"
    fetch_log = settings.data_dir / "logs" / "fetch-log.jsonl"
    summary = fetch_documents(
        documents, raw_dir, fetch_log, downloader or HttpDownloader(USER_AGENT)
    )
    logger.info(
        "wrote %s: %d downloaded, %d already present",
        raw_dir,
        len(summary.downloaded),
        len(summary.already_present),
    )

    return summary
