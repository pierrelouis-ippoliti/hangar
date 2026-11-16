import re
from typing import Any

import pytest

from hangar.chunking.chunker import ChunkError
from hangar.chunking.fixed import FixedTokenChunker
from hangar.chunking.tokens import WhitespaceCounter
from hangar.core.chunks import Chunk
from hangar.core.config import ChunkingConfig
from hangar.core.parsed import PageLocation, ParsedDocument, Passage, passage_id

DOCUMENT_ID = "example-handbook"
FAKE_SHA256 = "0123456789abcdef" * 4

# Page 1 is "one two three four\n\n" (0-20), page 2 is empty (20-20) and
# page 3 is "five six seven" (20-34). Words start at 0, 4, 8, 14, 20, 25, 29.
TEXT = "one two three four\n\nfive six seven"
PAGES = [(1, 0, 20), (2, 20, 20), (3, 20, 34)]


def document(
    text: str = TEXT, pages: list[tuple[int, int, int]] = PAGES
) -> ParsedDocument:
    passages = []

    for index, start, end in pages:
        location = PageLocation(page_index=index, page_label=f"7-{index}")
        passages.append(
            Passage(
                id=passage_id(DOCUMENT_ID, location),
                location=location,
                start=start,
                end=end,
            )
        )

    return ParsedDocument(
        document_id=DOCUMENT_ID,
        source_sha256=FAKE_SHA256,
        parser={"name": "example-parser", "version": "1.0"},
        text=text,
        passages=passages,
    )


def chunker(size: int = 3, overlap: int = 0, counter: Any = None) -> FixedTokenChunker:
    config = ChunkingConfig(
        type="fixed_tokens", size=size, overlap=overlap, tokenizer="embedder"
    )

    return FixedTokenChunker(counter or WhitespaceCounter(), config)


def spans(chunks: list[Chunk]) -> list[tuple[int, int]]:
    return [(c.start, c.end) for c in chunks]


class BigCountsTwice(WhitespaceCounter):
    """Places tokens like the whitespace counter, but counts "big" as two."""

    def count(self, text: str) -> int:
        return super().count(text) + len(re.findall(r"\bbig\b", text))


def test_chunks_are_cut_every_size_tokens() -> None:
    chunks = chunker(size=3).chunk(document())

    assert spans(chunks) == [(0, 14), (14, 29), (29, 34)]
    assert [c.text for c in chunks] == ["one two three ", "four\n\nfive six ", "seven"]


def test_token_counts_are_right_and_never_over_the_size() -> None:
    chunks = chunker(size=3).chunk(document())

    assert [c.token_count for c in chunks] == [3, 3, 1]


def test_chunks_cover_the_text_exactly_once() -> None:
    chunks = chunker(size=2).chunk(document())

    assert chunks[0].start == 0
    assert chunks[-1].end == len(TEXT)
    assert all(a.end == b.start for a, b in zip(chunks, chunks[1:], strict=False))
    assert "".join(c.text for c in chunks) == TEXT


def test_a_chunk_that_crosses_a_page_break_lists_both_pages() -> None:
    chunks = chunker(size=3).chunk(document())

    assert [p.id for p in chunks[1].passages] == [
        "example-handbook#p1",
        "example-handbook#p3",
    ]
    assert chunks[1].passages[1].location == PageLocation(
        page_index=3, page_label="7-3"
    )


def test_empty_pages_are_never_listed() -> None:
    chunks = chunker(size=100).chunk(document())

    assert len(chunks) == 1
    assert [p.id for p in chunks[0].passages] == [
        "example-handbook#p1",
        "example-handbook#p3",
    ]


def test_the_last_chunk_holds_what_is_left() -> None:
    chunks = chunker(size=3).chunk(document())

    assert chunks[-1].text == "seven"
    assert chunks[-1].token_count == 1


def test_leading_whitespace_belongs_to_the_first_chunk() -> None:
    text = "  one two"
    chunks = chunker(size=1).chunk(document(text, [(1, 0, len(text))]))

    assert spans(chunks) == [(0, 6), (6, 9)]


def test_a_chunk_that_counts_over_the_size_on_its_own_is_cut_earlier() -> None:
    text = "a big c d"
    chunks = chunker(size=3, counter=BigCountsTwice()).chunk(
        document(text, [(1, 0, len(text))])
    )

    assert [c.text for c in chunks] == ["a big ", "c d"]
    assert [c.token_count for c in chunks] == [3, 2]


def test_a_token_that_counts_over_the_size_on_its_own_stops_the_run() -> None:
    text = "big"

    with pytest.raises(ChunkError, match="^example-handbook: "):
        chunker(size=1, counter=BigCountsTwice()).chunk(
            document(text, [(1, 0, len(text))])
        )


def test_overlapping_chunks_share_their_last_tokens() -> None:
    chunks = chunker(size=3, overlap=1).chunk(document())

    assert [c.text for c in chunks] == [
        "one two three ",
        "three four\n\nfive ",
        "five six seven",
    ]


def test_chunk_ids_derive_from_the_chunker_and_stay_the_same() -> None:
    first = chunker(size=3).chunk(document())
    second = chunker(size=3).chunk(document())

    assert [c.id for c in first] == [c.id for c in second]
    assert {c.chunker_id for c in first} == {"fixed3"}


def test_a_text_without_tokens_stops_the_run() -> None:
    text = " \n "

    with pytest.raises(ChunkError, match="^example-handbook: .*no tokens"):
        chunker().chunk(document(text, [(1, 0, len(text))]))
