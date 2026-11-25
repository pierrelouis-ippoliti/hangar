"""
Citations: the sources an answer points to with markers such as [2].

The answer cites the numbered sources of its prompt. A marker whose number
is in the source map is valid, and traces to a chunk, its document and the
pages or sections it covers. A marker with any other number is invalid: it
points at no source. The answer record (#27) keeps both kinds.
"""

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    model_validator,
)

from hangar.core.chunks import CHUNK_ID_LENGTH, PassageRef
from hangar.core.corpus import DOCUMENT_ID_PATTERN


class Citation(BaseModel):
    """
    One source marker found in an answer.

    Attributes:
        marker: The number in the marker, such as 2 for ``[2]``.
        valid: Whether the number is in the source map.
        chunk_id: The cited chunk's ID, or None when the marker is invalid.
        document_id: The manifest ID of the cited chunk's document, or None
            when the marker is invalid.
        passages: The pages or sections the cited chunk covers, in text
            order; empty when the marker is invalid.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    marker: NonNegativeInt
    valid: bool
    chunk_id: str | None = Field(pattern=rf"^[0-9a-f]{{{CHUNK_ID_LENGTH}}}$")
    document_id: str | None = Field(pattern=DOCUMENT_ID_PATTERN)
    passages: tuple[PassageRef, ...]

    @model_validator(mode="after")
    def _check_source_matches_validity(self) -> Self:
        source_fields = (self.chunk_id, self.document_id, self.passages)

        if self.valid and not all(source_fields):
            raise ValueError(
                f"valid citation [{self.marker}] must name its chunk, "
                "its document and at least one passage"
            )

        if not self.valid and any(source_fields):
            raise ValueError(
                f"invalid citation [{self.marker}] must have no chunk, "
                "no document and no passages"
            )

        return self
