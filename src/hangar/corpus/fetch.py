"""
The fetch stage: download each document of a snapshot and check its hash.

Files go to the raw folder under their artifact ID, such as
``faa-h-8083-31b.pdf``. A file already there with the right hash is kept, so
a second run downloads nothing. Each download is added to the fetch log,
one raw artifact record per line. The log lives outside the raw folder, so
the folder holds only the documents and hashes the same on every machine.
"""

import logging
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from hangar.core.corpus import DocumentSpec, RawArtifact, raw_artifact_id
from hangar.core.errors import HangarError
from hangar.corpus.download import Downloader, DownloadError, file_sha256
from hangar.observability.logs import log_context

logger = logging.getLogger(__name__)


class FetchError(HangarError):
    """A document that couldn't be fetched. The message starts with its ID."""


@dataclass(frozen=True)
class FetchSummary:
    """
    What a fetch run did.

    Attributes:
        downloaded: The IDs of the documents downloaded, in manifest order.
        already_present: The IDs of the documents whose file was already
            there with the right hash.
    """

    downloaded: tuple[str, ...]
    already_present: tuple[str, ...]


def fetch_documents(
    documents: Sequence[DocumentSpec],
    raw_dir: Path,
    fetch_log: Path,
    downloader: Downloader,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FetchSummary:
    """
    Make sure each document's file is in the raw folder with the right hash.

    Documents are handled one at a time, in order. The first one that fails
    stops the run; the files fetched before it are kept.

    Args:
        documents: The documents to fetch, from the manifest.
        raw_dir: The raw folder. It is created if needed.
        fetch_log: The JSON lines file each download is added to. It and
            its folder are created if needed.
        downloader: What downloads each file.
        now: Gives the current time, recorded as each file's fetch time.

    Returns:
        Which documents were downloaded and which were already there.

    Raises:
        FetchError: If a file can't be downloaded or its SHA-256 differs
            from the manifest's. The message starts with the document ID.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    fetch_log.parent.mkdir(parents=True, exist_ok=True)
    downloaded, already_present = [], []

    for document in documents:
        with log_context(document_id=document.id):
            if _fetch_one(document, raw_dir, fetch_log, downloader, now):
                downloaded.append(document.id)
            else:
                already_present.append(document.id)

    return FetchSummary(tuple(downloaded), tuple(already_present))


def _fetch_one(
    document: DocumentSpec,
    raw_dir: Path,
    fetch_log: Path,
    downloader: Downloader,
    now: Callable[[], datetime],
) -> bool:
    """Fetch one document. Return False if its file was already there."""
    target = raw_dir / raw_artifact_id(document)

    if target.is_file() and file_sha256(target) == document.sha256:
        logger.info("already present: %s", target)

        return False

    # Write next to the target, then rename: an interrupted download never
    # leaves a file that looks complete.
    partial = target.with_name(target.name + ".part")
    url = str(document.source_url)
    logger.info("downloading %s", url)

    try:
        download = downloader.download(url, partial)

        if download.sha256 != document.sha256:
            raise FetchError(
                f"{document.id}: the file downloaded from {url} has SHA-256 "
                f"{download.sha256}, but the manifest expects {document.sha256}"
            )

        os.replace(partial, target)
    except DownloadError as error:
        raise FetchError(f"{document.id}: {error}") from error
    finally:
        partial.unlink(missing_ok=True)

    record = RawArtifact(
        id=target.name,
        document_id=document.id,
        path=str(target),
        sha256=download.sha256,
        size_bytes=download.size_bytes,
        fetched_at=now(),
        etag=download.etag,
        last_modified=download.last_modified,
    )

    with fetch_log.open("a", encoding="utf-8") as log:
        log.write(record.model_dump_json() + "\n")

    logger.info("downloaded %s, %d bytes", target, download.size_bytes)

    return True
