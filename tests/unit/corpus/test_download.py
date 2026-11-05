import gzip
import hashlib
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from hangar.corpus.download import (
    DownloadError,
    HttpDownloader,
    LocalCopyDownloader,
    file_sha256,
)

USER_AGENT = "hangar-tests/1.0"
ETAG = '"v1"'
LAST_MODIFIED = "Fri, 21 Jul 2023 14:02:11 GMT"


@dataclass
class FakeSite:
    """A web site on 127.0.0.1 that serves set pages and can fail on purpose."""

    url: str = ""
    pages: dict[str, bytes] = field(default_factory=dict)
    # Status codes a path answers, in order, before it serves its page.
    failures: dict[str, list[int]] = field(default_factory=dict)
    requests: list[tuple[str, str | None]] = field(default_factory=list)
    # The Content-Encoding a path is sent with, such as "gzip". "cut-gzip"
    # sends gzip with the second half of the data missing.
    encodings: dict[str, str] = field(default_factory=dict)


@pytest.fixture
def site() -> Iterator[FakeSite]:
    fake = FakeSite()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            fake.requests.append((self.path, self.headers.get("User-Agent")))
            failures = fake.failures.get(self.path, [])

            if failures:
                self.send_response(failures.pop(0))
                self.end_headers()
                return

            if self.path not in fake.pages:
                self.send_response(404)
                self.end_headers()
                return

            body = fake.pages[self.path]
            encoding = fake.encodings.get(self.path)

            if encoding in ("gzip", "cut-gzip"):
                body = gzip.compress(body)

            if encoding == "cut-gzip":
                body, encoding = body[: len(body) // 2], "gzip"

            self.send_response(200)

            if encoding:
                self.send_header("Content-Encoding", encoding)

            self.send_header("Content-Length", str(len(body)))
            self.send_header("ETag", ETAG)
            self.send_header("Last-Modified", LAST_MODIFIED)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    fake.url = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    yield fake
    server.shutdown()
    server.server_close()


class FakeTime:
    """A clock that moves only when the code under test sleeps."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def downloader(time: FakeTime, **changes: float) -> HttpDownloader:
    options: dict[str, float] = {
        "min_delay_seconds": 1.0,
        "attempts": 3,
        "backoff_seconds": 2.0,
    }
    options.update(changes)

    return HttpDownloader(
        USER_AGENT,
        min_delay_seconds=options["min_delay_seconds"],
        attempts=int(options["attempts"]),
        backoff_seconds=options["backoff_seconds"],
        sleep=time.sleep,
        clock=time.clock,
    )


def test_download_streams_the_file_and_returns_its_size_hash_and_validators(
    site: FakeSite, tmp_path: Path
) -> None:
    # Larger than one read, so the file is written in several pieces.
    body = bytes(range(256)) * 12_000
    site.pages["/handbook.pdf"] = body
    destination = tmp_path / "handbook.pdf"

    result = downloader(FakeTime()).download(f"{site.url}/handbook.pdf", destination)

    assert destination.read_bytes() == body
    assert result.size_bytes == len(body)
    assert result.sha256 == hashlib.sha256(body).hexdigest()
    assert (result.etag, result.last_modified) == (ETAG, LAST_MODIFIED)


def test_download_sends_the_user_agent(site: FakeSite, tmp_path: Path) -> None:
    site.pages["/page"] = b"text"

    downloader(FakeTime()).download(f"{site.url}/page", tmp_path / "page")

    assert site.requests == [("/page", USER_AGENT)]


def test_requests_are_spaced_by_the_minimum_delay(
    site: FakeSite, tmp_path: Path
) -> None:
    site.pages["/a"] = site.pages["/b"] = b"text"
    time = FakeTime()
    http = downloader(time, min_delay_seconds=1.5)

    http.download(f"{site.url}/a", tmp_path / "a")
    http.download(f"{site.url}/b", tmp_path / "b")

    assert time.sleeps == [1.5]


@pytest.mark.parametrize("status", [429, 500, 503])
def test_busy_or_failing_server_is_retried_with_a_growing_wait(
    site: FakeSite, tmp_path: Path, status: int
) -> None:
    site.pages["/page"] = b"text"
    site.failures["/page"] = [status, status]
    time = FakeTime()

    result = downloader(time, min_delay_seconds=0).download(
        f"{site.url}/page", tmp_path / "page"
    )

    assert result.size_bytes == 4
    assert len(site.requests) == 3
    assert time.sleeps == [2.0, 4.0]


def test_download_fails_after_the_last_attempt(site: FakeSite, tmp_path: Path) -> None:
    site.failures["/page"] = [503, 503, 503]

    with pytest.raises(DownloadError) as error_info:
        downloader(FakeTime()).download(f"{site.url}/page", tmp_path / "page")

    assert "503" in str(error_info.value)
    assert "3 attempts" in str(error_info.value)


def test_missing_page_is_not_retried(site: FakeSite, tmp_path: Path) -> None:
    with pytest.raises(DownloadError) as error_info:
        downloader(FakeTime()).download(f"{site.url}/gone", tmp_path / "gone")

    assert "404" in str(error_info.value)
    assert len(site.requests) == 1


def test_unreachable_server_is_retried_then_fails(tmp_path: Path) -> None:
    time = FakeTime()

    with pytest.raises(DownloadError):
        downloader(time, min_delay_seconds=0).download(
            "http://127.0.0.1:9/page", tmp_path / "page"
        )

    assert time.sleeps == [2.0, 4.0]


def test_local_copy_downloader_copies_the_file_for_a_known_url(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-fake")
    fake = LocalCopyDownloader({"https://example.org/a.pdf": source})

    result = fake.download("https://example.org/a.pdf", tmp_path / "copy.pdf")

    assert (tmp_path / "copy.pdf").read_bytes() == b"%PDF-fake"
    assert result.sha256 == file_sha256(source)
    assert result.size_bytes == 9
    assert fake.downloaded == ["https://example.org/a.pdf"]


def test_local_copy_downloader_refuses_an_unknown_url(tmp_path: Path) -> None:
    with pytest.raises(DownloadError):
        LocalCopyDownloader({}).download("https://example.org/x", tmp_path / "x")


def test_file_sha256_matches_hashlib(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_bytes(b"hangar")

    assert file_sha256(path) == hashlib.sha256(b"hangar").hexdigest()


def test_gzip_encoded_answer_is_saved_and_hashed_decoded(
    site: FakeSite, tmp_path: Path
) -> None:
    # The Wayback Machine replays pages gzip-encoded, even when not asked to.
    body = b"<html>" + b"standard text " * 200_000 + b"</html>"
    site.pages["/snapshot"] = body
    site.encodings["/snapshot"] = "gzip"
    destination = tmp_path / "snapshot.html"

    result = downloader(FakeTime()).download(f"{site.url}/snapshot", destination)

    assert destination.read_bytes() == body
    assert result.size_bytes == len(body)
    assert result.sha256 == hashlib.sha256(body).hexdigest()


def test_unknown_content_encoding_fails_without_a_retry(
    site: FakeSite, tmp_path: Path
) -> None:
    site.pages["/page"] = b"text"
    site.encodings["/page"] = "br"

    with pytest.raises(DownloadError) as error_info:
        downloader(FakeTime()).download(f"{site.url}/page", tmp_path / "page")

    assert "br" in str(error_info.value)
    assert len(site.requests) == 1


def test_gzip_data_that_ends_early_is_retried_then_fails(
    site: FakeSite, tmp_path: Path
) -> None:
    site.pages["/snapshot"] = bytes(range(256)) * 1000
    site.encodings["/snapshot"] = "cut-gzip"

    with pytest.raises(DownloadError) as error_info:
        downloader(FakeTime(), min_delay_seconds=0).download(
            f"{site.url}/snapshot", tmp_path / "snapshot"
        )

    assert "ended early" in str(error_info.value)
    assert len(site.requests) == 3
