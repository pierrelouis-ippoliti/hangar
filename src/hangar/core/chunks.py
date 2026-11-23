"""
Chunks: the pieces of a canonical text that are embedded and searched.

A chunker splits each document's canonical text into chunks, which together
cover it exactly once. A chunk is a range of that text, so the pages or
sections it covers are found from its offsets, never guessed.

A chunk's ID is a short hash of its document, its chunker and its offsets,
so it stays the same from one run to the next, and changes when the parse or
the chunker changes.
"""

import hashlib
from collections.abc import Sequence
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    model_validator,
)

from hangar.core.config import ChunkingConfig, CommitHash
from hangar.core.corpus import DOCUMENT_ID_PATTERN, SHA256_PATTERN
from hangar.core.parsed import Location, PageLocation

# 16 hex characters are 64 bits: a collision among a few million chunks is
# very unlikely, and the ID still fits in a Qdrant point ID.
CHUNK_ID_LENGTH = 16


class ChunkModel(BaseModel):
    """
    A part of a chunk: frozen, and with no unknown fields.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class PassageRef(ChunkModel):
    """
    A page or section that a chunk covers, even in part.

    Attributes:
        id: The passage ID, such as ``faa-h-8083-31b#p142``.
        location: Where the passage sits, so a citation can show the printed
            page label or the section number without the parsed file.
    """

    id: str = Field(min_length=1)
    location: Location


def chunk_id(document_id: str, chunker: str, start: int, end: int) -> str:
    """
    Derive a chunk's ID from its document, chunker and offsets.

    Args:
        document_id: The manifest ID of the document.
        chunker: The chunker ID, from ``chunker_id``.
        start: The offset of the chunk's first character.
        end: The offset just after its last character.

    Returns:
        The first 16 hex characters of the SHA-256 of
        ``<document>|<chunker>|<start>|<end>``.
    """
    key = f"{document_id}|{chunker}|{start}|{end}"

    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:CHUNK_ID_LENGTH]


def chunker_id(config: ChunkingConfig) -> str:
    """
    Name a chunker configuration, for chunk IDs, folders and collections.

    Args:
        config: The chunking section of the pipeline configuration.

    Returns:
        ``fixed<size>``, such as ``fixed512``, followed by ``-o<overlap>``
        when chunks overlap, such as ``fixed256-o32``.
    """
    name = f"fixed{config.size}"

    if config.overlap:
        name += f"-o{config.overlap}"

    return name


def describe_passages(passages: Sequence[PassageRef]) -> str:
    """
    Name the pages or sections a chunk covers, for a reader.

    A page shows its index, and its printed label in brackets when the PDF
    has one. A section shows ``§`` and its number, and the text before the
    first numbered section shows as ``front matter``.

    Args:
        passages: The passages, in text order. At least one.

    Returns:
        The first passage, such as ``p. 323 (7-79)`` or ``§ 571.10``, or the
        first and last joined by ``to`` when there are several, such as
        ``p. 323 (7-79) to p. 324 (7-80)``.
    """
    first, last = passages[0], passages[-1]

    if first == last:
        return _describe_passage(first)

    return f"{_describe_passage(first)} to {_describe_passage(last)}"


def _describe_passage(passage: PassageRef) -> str:
    location = passage.location

    if isinstance(location, PageLocation):
        if location.page_label is None:
            return f"p. {location.page_index}"

        return f"p. {location.page_index} ({location.page_label})"

    if location.label is None:
        return "front matter"

    return f"§ {location.label}"


class Chunk(ChunkModel):
    """
    One chunk of a document's canonical text.

    Attributes:
        id: The ID from ``chunk_id``.
        document_id: The manifest ID of the document.
        chunker_id: The chunker that made the chunk, from ``chunker_id``.
        start: The offset of the chunk's first character in the canonical
            text.
        end: The offset just after its last character.
        text: The chunk's text, the canonical text from ``start`` to ``end``.
        token_count: How many tokens the text has, counted with the
            embedder's tokenizer, without the special tokens it adds.
        passages: The pages or sections the chunk covers, even in part, in
            text order.
    """

    id: str = Field(pattern=rf"^[0-9a-f]{{{CHUNK_ID_LENGTH}}}$")
    document_id: str = Field(pattern=DOCUMENT_ID_PATTERN)
    chunker_id: str = Field(min_length=1)
    start: NonNegativeInt
    end: PositiveInt
    text: str
    token_count: PositiveInt
    passages: tuple[PassageRef, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_offsets_and_id(self) -> Self:
        if self.end <= self.start:
            raise ValueError(
                f"chunk of {self.document_id}: end ({self.end}) must come after "
                f"start ({self.start})"
            )

        if len(self.text) != self.end - self.start:
            raise ValueError(
                f"chunk of {self.document_id} at {self.start}-{self.end}: the text "
                f"has {len(self.text)} characters, not {self.end - self.start}"
            )

        expected = chunk_id(self.document_id, self.chunker_id, self.start, self.end)

        if self.id != expected:
            raise ValueError(
                f"chunk {self.id} should have the ID {expected}, "
                "from its document, chunker and offsets"
            )

        return self


class TokenizerInfo(ChunkModel):
    """
    The tokenizer that counted a chunk set's tokens.

    Attributes:
        model: The Hugging Face model ID, such as ``BAAI/bge-m3``.
        revision: The model's commit hash.
    """

    model: str = Field(min_length=1)
    revision: CommitHash


Sha256 = Annotated[str, Field(pattern=SHA256_PATTERN)]


class ChunksMeta(ChunkModel):
    """
    Where a chunk set came from: the ``meta.json`` next to ``chunks.jsonl``.

    It holds only values that change with the chunks, so two runs with the
    same inputs write the same file.

    Attributes:
        snapshot: The corpus snapshot, such as ``c1``.
        chunker_id: The chunker, such as ``fixed512``.
        config_hash: The hash of the pipeline configuration of the run.
        tokenizer: The tokenizer that counted the tokens.
        parsed_files: The SHA-256 of each parsed file that was read, keyed
            by document ID.
        chunks: How many chunks were written.
        tokens: How many tokens the chunks hold in all.
    """

    snapshot: str = Field(min_length=1)
    chunker_id: str = Field(min_length=1)
    config_hash: Sha256
    tokenizer: TokenizerInfo
    parsed_files: dict[str, Sha256] = Field(min_length=1)
    chunks: PositiveInt
    tokens: PositiveInt

    @property
    def documents(self) -> int:
        """
        How many documents were chunked.
        """
        return len(self.parsed_files)
