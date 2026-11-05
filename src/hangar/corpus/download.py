"""
Downloading a document to a file.

``Downloader`` is the interface the fetch stage uses. ``HttpDownloader``
downloads over HTTP with the standard library; ``LocalCopyDownloader``
copies local files instead, so tests never touch the network.
"""

import hashlib
import http.client
import time
import urllib.error
import urllib.request
import zlib
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Protocol

from hangar.core.errors import HangarError

# Read, decode and hash files 1 MiB at a time, so a 205 MB PDF never sits
# in memory.
CHUNK_BYTES = 1024 * 1024

# No document may be larger than this once decoded. The largest in C1, the
# Powerplant handbook, is 215 MB; the limit stops a runaway download or a
# small gzip answer that would decode to gigabytes.
MAX_DOWNLOAD_BYTES = 10**9

# Statuses that mean "try again later" rather than "this will never work".
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

# Content-Encoding values the downloader can undo. The Wayback Machine sends
# gzip even to a client that asks for none, so gzip must be handled.
GZIP_ENCODINGS = frozenset({"gzip", "x-gzip"})


class DownloadError(HangarError):
    """A file that couldn't be downloaded."""


@dataclass(frozen=True)
class Download:
    """
    What a download wrote.

    Attributes:
        size_bytes: The size of the file written.
        sha256: The file's SHA-256, as 64 lowercase hex characters.
        etag: The server's ``ETag`` header, or None if it sent none.
        last_modified: The server's ``Last-Modified`` header, or None if it
            sent none.
    """

    size_bytes: int
    sha256: str
    etag: str | None = None
    last_modified: str | None = None


class Downloader(Protocol):
    """Something that downloads a URL to a file."""

    def download(self, url: str, destination: Path) -> Download:
        """
        Download a URL to a file, replacing the file if it exists.

        Args:
            url: Where to download from.
            destination: The file to write. Its folder must exist.

        Returns:
            The size, hash and HTTP validators of what was written.

        Raises:
            DownloadError: If the file can't be downloaded.
        """
        ...


class HttpDownloader:
    """
    Download over HTTP, politely: one request at a time, spaced out, retried.

    Busy or failing servers (429 and 5xx statuses) and network errors are
    retried, waiting ``backoff_seconds``, then twice that, and so on. Other
    statuses, such as 404, fail at once.

    A gzip-encoded answer is decoded while it streams, so the file written
    and its hash are those of the document itself.
    """

    def __init__(
        self,
        user_agent: str,
        *,
        min_delay_seconds: float = 1.0,
        attempts: int = 3,
        backoff_seconds: float = 2.0,
        timeout_seconds: float = 60.0,
        max_bytes: int = MAX_DOWNLOAD_BYTES,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """
        Create the downloader.

        Args:
            user_agent: The ``User-Agent`` header sent with every request.
            min_delay_seconds: The shortest time between two requests,
                retries included.
            attempts: How many times a URL is tried before giving up.
            backoff_seconds: The wait before the first retry. It doubles
                with each retry.
            timeout_seconds: How long to wait for the server to answer.
            max_bytes: The largest file accepted, once decoded. A larger one
                fails at once, without a retry.
            sleep: Waits a number of seconds. Tests replace it.
            clock: Gives the current time in seconds. Tests replace it.
        """
        self._user_agent = user_agent
        self._min_delay = min_delay_seconds
        self._attempts = attempts
        self._backoff = backoff_seconds
        self._timeout = timeout_seconds
        self._max_bytes = max_bytes
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None

    def download(self, url: str, destination: Path) -> Download:
        """
        Download a URL to a file, streaming it to disk.

        Args:
            url: Where to download from.
            destination: The file to write. Its folder must exist.

        Returns:
            The size, hash and HTTP validators of what was written.

        Raises:
            DownloadError: If the server refuses the request, or every
                attempt fails.
        """
        reason = ""

        for attempt in range(1, self._attempts + 1):
            if attempt > 1:
                self._sleep(self._backoff * 2 ** (attempt - 2))

            self._wait_for_turn()

            try:
                return self._get(url, destination)
            except urllib.error.HTTPError as error:
                if error.code not in RETRYABLE_STATUSES:
                    raise DownloadError(f"{url} answered {error.code}") from error

                reason = f"it answered {error.code}"
            except (OSError, http.client.HTTPException, zlib.error) as error:
                reason = str(getattr(error, "reason", error))

        raise DownloadError(
            f"can't download {url}: {reason}, after {self._attempts} attempts"
        )

    def _wait_for_turn(self) -> None:
        if self._last_request is not None:
            wait = self._last_request + self._min_delay - self._clock()

            if wait > 0:
                self._sleep(wait)

        self._last_request = self._clock()

    def _get(self, url: str, destination: Path) -> Download:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": self._user_agent, "Accept-Encoding": "identity"},
        )

        with urllib.request.urlopen(request, timeout=self._timeout) as response:
            encoding = response.headers.get("Content-Encoding", "identity").lower()

            if encoding in GZIP_ENCODINGS:
                # 16 + MAX_WBITS: expect a gzip header and trailer.
                decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
            elif encoding == "identity":
                decoder = None
            else:
                raise DownloadError(
                    f"{url} was sent with Content-Encoding {encoding!r}, "
                    "which Hangar can't decode"
                )

            with destination.open("wb") as file:
                size, sha256 = _copy_and_hash(
                    response, file, decoder, max_bytes=self._max_bytes
                )

            if size > self._max_bytes:
                raise DownloadError(
                    f"{url} is larger than the {self._max_bytes} bytes allowed"
                )

            return Download(
                size_bytes=size,
                sha256=sha256,
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
            )


@dataclass
class LocalCopyDownloader:
    """
    A downloader for tests: it copies a local file for each known URL.

    Attributes:
        files: The local file to copy for each URL.
        downloaded: The URLs downloaded so far, in order.
    """

    files: Mapping[str, Path]
    downloaded: list[str] = field(default_factory=list)

    def download(self, url: str, destination: Path) -> Download:
        """
        Copy the file known for a URL.

        Args:
            url: One of the URLs in ``files``.
            destination: The file to write.

        Returns:
            The size and hash of the copy, with no HTTP validators.

        Raises:
            DownloadError: If the URL is not in ``files``.
        """
        if url not in self.files:
            raise DownloadError(f"{url} answered 404")

        self.downloaded.append(url)

        with self.files[url].open("rb") as source, destination.open("wb") as file:
            size, sha256 = _copy_and_hash(source, file)

        return Download(size_bytes=size, sha256=sha256)


def file_sha256(path: Path) -> str:
    """
    Compute a file's SHA-256 without reading it all into memory.

    Args:
        path: The file.

    Returns:
        The SHA-256, as 64 lowercase hex characters.
    """
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(CHUNK_BYTES):
            digest.update(chunk)

    return digest.hexdigest()


def _copy_and_hash(
    source: BinaryIO | http.client.HTTPResponse,
    target: BinaryIO,
    decoder: "zlib._Decompress | None" = None,
    *,
    max_bytes: int | None = None,
) -> tuple[int, str]:
    """Copy and hash the source; stop once more than max_bytes were read."""
    digest = hashlib.sha256()
    size = 0

    for chunk in _chunks(source, decoder):
        size += len(chunk)

        if max_bytes is not None and size > max_bytes:
            break

        digest.update(chunk)
        target.write(chunk)

    return size, digest.hexdigest()


def _chunks(
    source: BinaryIO | http.client.HTTPResponse,
    decoder: "zlib._Decompress | None",
) -> Iterator[bytes]:
    while chunk := source.read(CHUNK_BYTES):
        if decoder is None:
            yield chunk
            continue

        # Decode at most CHUNK_BYTES at a time: one chunk of gzip data can
        # decode to far more than that.
        pending = chunk

        while pending:
            yield decoder.decompress(pending, CHUNK_BYTES)
            pending = decoder.unconsumed_tail

    if decoder:
        yield decoder.flush()

        if not decoder.eof:
            raise zlib.error("the gzip data ended early")
