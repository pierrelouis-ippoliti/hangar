"""
The chunker interface: what every chunker provides.

v0 has one chunker, a fixed number of tokens per chunk. v2 adds a
structure-aware chunker, chosen by configuration, which is why chunkers sit
behind this interface.
"""

from typing import Protocol

from hangar.core.chunks import Chunk
from hangar.core.errors import HangarError
from hangar.core.parsed import ParsedDocument


class ChunkError(HangarError):
    """
    A document that couldn't be chunked.

    The message starts with the document ID.
    """


class Chunker(Protocol):
    """
    Splits a parsed document into chunks.

    Attributes:
        id: The chunker ID, such as ``fixed512``, written in every chunk.
    """

    id: str

    def chunk(self, document: ParsedDocument) -> list[Chunk]:
        """
        Split one parsed document into chunks.

        Args:
            document: The parsed document. It is read, never changed.

        Returns:
            The chunks, in text order.

        Raises:
            ChunkError: If the document can't be split under the
                configured size.
        """
        ...
