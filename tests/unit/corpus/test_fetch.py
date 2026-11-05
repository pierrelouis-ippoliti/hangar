import datetime
import hashlib
from pathlib import Path

import pytest

from hangar.core.corpus import DocumentSpec, RawArtifact
from hangar.corpus.download import LocalCopyDownloader
from hangar.corpus.fetch import FetchError, fetch_documents

FETCHED_AT = datetime.datetime(2026, 11, 5, 9, 30, tzinfo=datetime.UTC)
WRONG_SHA256 = "f" * 64


def spec(document_id: str, document_format: str, content: bytes) -> DocumentSpec:
    return DocumentSpec.model_validate(
        {
            "id": document_id,
            "title": "Example",
            "authority": "FAA",
            "type": "handbook",
            "language": "en",
            "source_url": f"https://example.org/{document_id}",
            "official_url": f"https://example.org/{document_id}",
            "format": document_format,
            "edition": "B",
            "content_date": "2023-01-01",
            "page_modified_date": "2023-01-01",
            "retrieved_on": "2026-11-04",
            "status": "active",
            "sha256": hashlib.sha256(content).hexdigest(),
            "reuse_note": "Made up for tests.",
        }
    )


@pytest.fixture
def corpus(tmp_path: Path) -> tuple[list[DocumentSpec], LocalCopyDownloader]:
    """Three documents, and a fake downloader that serves their files."""
    contents = {
        ("example-handbook", "pdf"): b"%PDF-fake handbook",
        ("example-regulation", "xml"): b"<Regulation/>",
        ("example-circular", "html"): b"<html>circular</html>",
    }
    sources = tmp_path / "sources"
    sources.mkdir()
    documents, files = [], {}

    for (document_id, document_format), content in contents.items():
        source = sources / document_id
        source.write_bytes(content)
        document = spec(document_id, document_format, content)
        documents.append(document)
        files[str(document.source_url)] = source

    return documents, LocalCopyDownloader(files)


def fetch_log(path: Path) -> list[RawArtifact]:
    lines = path.read_text().splitlines()

    return [RawArtifact.model_validate_json(line) for line in lines]


def test_every_document_is_downloaded_under_its_artifact_id(
    corpus: tuple[list[DocumentSpec], LocalCopyDownloader], tmp_path: Path
) -> None:
    documents, downloader = corpus
    raw_dir = tmp_path / "data" / "raw"
    log = tmp_path / "logs" / "fetch-log.jsonl"

    summary = fetch_documents(
        documents, raw_dir, log, downloader, now=lambda: FETCHED_AT
    )

    assert sorted(p.name for p in raw_dir.iterdir()) == [
        "example-circular.html",
        "example-handbook.pdf",
        "example-regulation.xml",
    ]
    assert summary.downloaded == (
        "example-handbook",
        "example-regulation",
        "example-circular",
    )
    assert summary.already_present == ()


def test_each_download_is_recorded_in_the_fetch_log(
    corpus: tuple[list[DocumentSpec], LocalCopyDownloader], tmp_path: Path
) -> None:
    documents, downloader = corpus
    raw_dir = tmp_path / "raw"
    log = tmp_path / "logs" / "fetch-log.jsonl"

    fetch_documents(documents, raw_dir, log, downloader, now=lambda: FETCHED_AT)

    records = fetch_log(log)
    assert [r.document_id for r in records] == [d.id for d in documents]
    first = records[0]
    assert first.id == "example-handbook.pdf"
    assert first.path == str(raw_dir / "example-handbook.pdf")
    assert first.sha256 == documents[0].sha256
    assert first.size_bytes == len(b"%PDF-fake handbook")
    assert first.fetched_at == FETCHED_AT


def test_second_run_downloads_nothing(
    corpus: tuple[list[DocumentSpec], LocalCopyDownloader], tmp_path: Path
) -> None:
    documents, downloader = corpus
    raw_dir = tmp_path / "raw"
    log = tmp_path / "logs" / "fetch-log.jsonl"
    fetch_documents(documents, raw_dir, log, downloader)
    log_before = log.read_text()
    downloader.downloaded.clear()

    summary = fetch_documents(documents, raw_dir, log, downloader)

    assert downloader.downloaded == []
    assert summary.downloaded == ()
    assert summary.already_present == tuple(d.id for d in documents)
    assert log.read_text() == log_before


def test_file_present_with_the_wrong_hash_is_downloaded_again(
    corpus: tuple[list[DocumentSpec], LocalCopyDownloader], tmp_path: Path
) -> None:
    documents, downloader = corpus
    raw_dir = tmp_path / "raw"
    log = tmp_path / "logs" / "fetch-log.jsonl"
    raw_dir.mkdir()
    (raw_dir / "example-handbook.pdf").write_bytes(b"truncated")

    summary = fetch_documents(documents[:1], raw_dir, log, downloader)

    assert summary.downloaded == ("example-handbook",)
    assert (raw_dir / "example-handbook.pdf").read_bytes() == b"%PDF-fake handbook"


def test_hash_mismatch_stops_the_run_with_an_error_naming_the_document(
    corpus: tuple[list[DocumentSpec], LocalCopyDownloader], tmp_path: Path
) -> None:
    documents, downloader = corpus
    documents[1] = documents[1].model_copy(update={"sha256": WRONG_SHA256})
    raw_dir = tmp_path / "raw"
    log = tmp_path / "logs" / "fetch-log.jsonl"

    with pytest.raises(FetchError) as error_info:
        fetch_documents(documents, raw_dir, log, downloader)

    message = str(error_info.value)
    assert message.startswith("example-regulation:")
    assert WRONG_SHA256 in message
    assert hashlib.sha256(b"<Regulation/>").hexdigest() in message
    # The run stopped there: the next document was never downloaded.
    assert downloader.downloaded == [
        "https://example.org/example-handbook",
        "https://example.org/example-regulation",
    ]
    # The bad file is not kept, and only the good download is recorded.
    assert sorted(p.name for p in raw_dir.iterdir()) == [
        "example-handbook.pdf",
    ]
    assert [r.document_id for r in fetch_log(log)] == ["example-handbook"]


def test_download_failure_stops_the_run_with_an_error_naming_the_document(
    corpus: tuple[list[DocumentSpec], LocalCopyDownloader], tmp_path: Path
) -> None:
    documents, _ = corpus
    raw_dir = tmp_path / "raw"
    log = tmp_path / "logs" / "fetch-log.jsonl"

    with pytest.raises(FetchError) as error_info:
        fetch_documents(documents, raw_dir, log, LocalCopyDownloader({}))

    assert str(error_info.value).startswith("example-handbook:")
    assert list(raw_dir.iterdir()) == []
