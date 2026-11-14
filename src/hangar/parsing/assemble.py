"""
Building a canonical text and its passages from the parts a parser extracts.

Every parser cuts its document into parts, one per page or section, and
hands them to ``assemble``. Building the offsets in one place means the
passages cover the text exactly once by construction, for every format.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from hangar.core.config import NormalisationConfig
from hangar.core.parsed import PageLocation, Passage, SectionLocation, passage_id
from hangar.parsing.normalise import normalise

# Put between two parts, so the text keeps a paragraph break where one page
# or section ends and the next begins.
PART_SEPARATOR = "\n\n"


@dataclass(frozen=True)
class TextPart:
    """
    One page or section, as extracted, before normalisation.

    Attributes:
        location: The page or section the text comes from.
        text: The extracted text.
    """

    location: PageLocation | SectionLocation
    text: str


def assemble(
    document_id: str, parts: Sequence[TextPart], normalisation: NormalisationConfig
) -> tuple[str, tuple[Passage, ...]]:
    """
    Join the parts into one canonical text, with one passage per part.

    Each part is normalised, then trimmed. A separator follows each part
    that has text, unless no later part has any, and it belongs to that
    part's passage. A part with no text, such as a blank page, keeps a
    zero-length passage, so page numbers stay continuous.

    Args:
        document_id: The manifest ID of the document, used in passage IDs.
        parts: The pages or sections, in document order.
        normalisation: The clean-up applied to each part.

    Returns:
        The canonical text, and the passages that cover it, in order.
    """
    pieces = [normalise(part.text, normalisation).strip() for part in parts]
    last_with_text = max((i for i, piece in enumerate(pieces) if piece), default=-1)
    text, passages = "", []

    for i, (part, piece) in enumerate(zip(parts, pieces, strict=True)):
        if piece and i < last_with_text:
            piece += PART_SEPARATOR

        passages.append(
            Passage(
                id=passage_id(document_id, part.location),
                location=part.location,
                start=len(text),
                end=len(text) + len(piece),
            )
        )
        text += piece

    return text, tuple(passages)
