"""
Builders for the domain objects that more than one test module needs.

Each builder fills in valid defaults, so a test names only the fields it
cares about.
"""

import datetime
from typing import Any

from hangar.core.chunks import Chunk, PassageRef, chunk_id
from hangar.core.corpus import DocumentSpec
from hangar.core.parsed import PageLocation, SectionLocation
from hangar.core.retrieval import ScoredChunk

DOCUMENT_ID = "example-handbook"
CHUNKER_ID = "fixed512"


def page(
    index: int = 1, label: str | None = None, *, document_id: str = DOCUMENT_ID
) -> PassageRef:
    """
    A reference to one page of a PDF document.
    """
    return PassageRef(
        id=f"{document_id}#p{index}",
        location=PageLocation(page_index=index, page_label=label),
    )


def section(
    label: str | None,
    *,
    document_id: str = "tc-std-571",
    heading_path: tuple[str, ...] = ("Standard 571",),
) -> PassageRef:
    """
    A reference to one section, or to the front matter when the label is None.
    """
    passage_id = f"{document_id}#s{label}" if label else f"{document_id}#front"

    return PassageRef(
        id=passage_id,
        location=SectionLocation(label=label, heading_path=heading_path),
    )


def chunk(
    text: str = "torque the bolt",
    *,
    start: int = 0,
    document_id: str | None = None,
    passages: list[PassageRef] | None = None,
) -> Chunk:
    """
    A chunk of the given text, with its ID computed from its offsets.

    Args:
        text: The chunk's text. Its token count is its number of words.
        start: The offset of its first character in the canonical text.
        document_id: The document it comes from. By default, the document of
            its first passage, or ``example-handbook`` without passages.
        passages: The passages it covers. By default, page 1 of the document.

    Returns:
        The chunk, made by the fixed512 chunker.
    """
    if passages is None:
        passages = [page(document_id=document_id or DOCUMENT_ID)]

    if document_id is None:
        document_id = passages[0].id.split("#")[0]

    end = start + len(text)

    return Chunk(
        id=chunk_id(document_id, CHUNKER_ID, start, end),
        document_id=document_id,
        chunker_id=CHUNKER_ID,
        start=start,
        end=end,
        text=text,
        token_count=len(text.split()),
        passages=passages,
    )


def consecutive_chunks(
    texts: list[str], *, document_id: str = DOCUMENT_ID
) -> list[Chunk]:
    """
    Chunks that follow one another from offset 0, one per text.
    """
    chunks, start = [], 0

    for text in texts:
        chunks.append(chunk(text, start=start, document_id=document_id))
        start += len(text)

    return chunks


def scored(
    scored_chunk: Chunk | None = None,
    *,
    score: float = 0.71,
    rank: int = 1,
    retriever_id: str = "dense",
) -> ScoredChunk:
    """
    A retrieval result for the given chunk, or for the default chunk.
    """
    return ScoredChunk(
        chunk=scored_chunk or chunk(),
        score=score,
        rank=rank,
        retriever_id=retriever_id,
    )


def document_spec(**changes: Any) -> DocumentSpec:
    """
    The manifest entry of an FAA handbook, with the given fields changed.

    Args:
        **changes: Field values that replace the defaults, such as
            ``id="tc-std-571"`` or ``format="html"``.

    Returns:
        The validated document spec.
    """
    fields: dict[str, Any] = {
        "id": "faa-h-8083-30b",
        "title": "Aviation Maintenance Technician Handbook – General",
        "authority": "FAA",
        "type": "handbook",
        "language": "en",
        "source_url": "https://example.org/handbook.pdf",
        "official_url": "https://example.org/handbook.pdf",
        "format": "pdf",
        "edition": "B",
        "content_date": datetime.date(2023, 7, 21),
        "page_modified_date": datetime.date(2023, 7, 27),
        "retrieved_on": datetime.date(2026, 11, 4),
        "status": "active",
        "sha256": "0123456789abcdef" * 4,
        "reuse_note": "Made up for tests.",
    }
    fields.update(changes)

    return DocumentSpec.model_validate(fields)
