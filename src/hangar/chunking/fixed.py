"""
The fixed-token chunker: each chunk holds at most a set number of tokens.

The text is tokenized once, and chunks are cut where a token starts, so no
token is split. A tokenizer can count a piece of text on its own a little
differently from the same piece inside the whole text, so each chunk's text
is counted again, and its end moves back one token at a time until the count
fits.
"""

from hangar.chunking.chunker import ChunkError
from hangar.chunking.tokens import TokenCounter
from hangar.core.chunks import Chunk, PassageRef, chunk_id, chunker_id
from hangar.core.config import ChunkingConfig
from hangar.core.parsed import ParsedDocument


class FixedTokenChunker:
    """
    Splits a canonical text into chunks of at most ``size`` tokens.

    With no overlap, the chunks cover the text exactly once: the first starts
    at 0, each one ends where the next starts, and the last ends at the end
    of the text. Whitespace before the first token belongs to the first
    chunk; whitespace after a token belongs to the chunk of that token.

    Attributes:
        id: The chunker ID, such as ``fixed512``.
    """

    def __init__(self, counter: TokenCounter, config: ChunkingConfig) -> None:
        """
        Set up the chunker.

        Args:
            counter: Counts tokens the way the embedder sees them.
            config: The chunking section of the pipeline configuration: the
                size and overlap, in tokens.
        """
        self.id = chunker_id(config)
        self._counter = counter
        self._size = config.size
        self._overlap = config.overlap

    def chunk(self, document: ParsedDocument) -> list[Chunk]:
        """
        Split one parsed document into chunks.

        Args:
            document: The parsed document. It is read, never changed.

        Returns:
            The chunks, in text order.

        Raises:
            ChunkError: If the text has no tokens, or a single token counts
                over the size on its own.
        """
        text = document.text
        starts = self._counter.token_starts(text)

        if not starts:
            raise ChunkError(f"{document.document_id}: the text has no tokens")

        chunks = []
        first = 0

        while True:
            last, token_count = self._fit(document, starts, first)
            start, end = _offsets(text, starts, first, last)
            chunks.append(self._make_chunk(document, start, end, token_count))

            if last == len(starts):
                return chunks

            first = max(last - self._overlap, first + 1)

    def _fit(
        self, document: ParsedDocument, starts: list[int], first: int
    ) -> tuple[int, int]:
        # Find the largest token index `last` such that the text from token
        # `first` to token `last` counts at most `size` tokens on its own.
        text = document.text
        last = min(first + self._size, len(starts))

        while last > first:
            start, end = _offsets(text, starts, first, last)
            token_count = self._counter.count(text[start:end])

            if token_count <= self._size:
                return last, token_count

            last -= 1

        raise ChunkError(
            f"{document.document_id}: the token at offset {starts[first]} counts over "
            f"{self._size} tokens on its own"
        )

    def _make_chunk(
        self, document: ParsedDocument, start: int, end: int, token_count: int
    ) -> Chunk:
        passages = document.passages_in_range(start, end)

        return Chunk(
            id=chunk_id(document.document_id, self.id, start, end),
            document_id=document.document_id,
            chunker_id=self.id,
            start=start,
            end=end,
            text=document.text[start:end],
            token_count=token_count,
            passages=tuple(PassageRef(id=p.id, location=p.location) for p in passages),
        )


def _offsets(text: str, starts: list[int], first: int, last: int) -> tuple[int, int]:
    # The character range from token `first` up to token `last`, which is
    # not included. The first chunk starts at 0 and the last one ends at the
    # end of the text, so no whitespace is left out.
    start = 0 if first == 0 else starts[first]
    end = starts[last] if last < len(starts) else len(text)

    return start, end
