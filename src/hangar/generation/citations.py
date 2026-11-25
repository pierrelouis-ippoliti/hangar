"""
The citation parser: an answer and its source map in; citations out.

The v0 prompt asks for one marker per source, such as ``[2]`` or
``[1][3]``, so only a number in square brackets counts as a marker. A
marker whose number is not in the source map gives an invalid citation.
"""

import re
from collections.abc import Sequence

from hangar.core.citations import Citation
from hangar.core.prompts import Source

MARKER = re.compile(r"\[([0-9]+)\]")


def parse_citations(answer: str, sources: Sequence[Source]) -> tuple[Citation, ...]:
    """
    Find the source markers in an answer and trace each one to its source.

    Args:
        answer: The text the language model wrote.
        sources: The source map of the prompt the answer replies to.

    Returns:
        One citation per distinct marker number, in the order each number
        first appears. A number in the source map gives a valid citation
        with its chunk, document and passages; any other number gives an
        invalid one. An answer with no marker gives an empty tuple.
    """
    by_number = {source.number: source for source in sources}
    markers = dict.fromkeys(int(number) for number in MARKER.findall(answer))

    return tuple(_cite(marker, by_number.get(marker)) for marker in markers)


def _cite(marker: int, source: Source | None) -> Citation:
    if source is None:
        return Citation(
            marker=marker,
            valid=False,
            chunk_id=None,
            document_id=None,
            passages=(),
        )

    return Citation(
        marker=marker,
        valid=True,
        chunk_id=source.chunk_id,
        document_id=source.document_id,
        passages=source.passages,
    )
