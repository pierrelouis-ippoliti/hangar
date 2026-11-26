"""
How an answer is shown to a reader: its sources, their attributions, the notice.

Every source an answer cites is shown with its document, its pages or
sections, its authority and type, its content date, and the attribution
that ``NOTICE.md`` asks for: the full title, the publisher and the official
URL (ADR-0003). Every answer ends with the study-aid notice.
"""

from collections.abc import Mapping

from hangar.core.chunks import describe_passages
from hangar.core.citations import Citation
from hangar.core.corpus import Authority, DocumentSpec, DocumentType
from hangar.core.records import AnswerRecord

STUDY_AID_NOTICE = (
    "Hangar is a study and lookup aid, not approved maintenance data. "
    "Its answers can be wrong or incomplete. Always check the current official "
    "documents and follow your organisation's approved procedures."
)

# A source's label joins its authority and its type, such as "FAA handbook
# guidance" or "Transport Canada advisory circular", so a reader, and the
# model, can tell guidance from requirements.
AUTHORITY_NAMES: dict[Authority, str] = {"FAA": "FAA", "TC": "Transport Canada"}
TYPE_NAMES: dict[DocumentType, str] = {
    "handbook": "handbook guidance",
    "regulation": "regulation",
    "standard": "standard",
    "advisory_circular": "advisory circular",
}


def source_label(document: DocumentSpec) -> str:
    """
    Name a document's authority and type.

    Args:
        document: The document's manifest entry.

    Returns:
        A label such as ``FAA handbook guidance`` or ``Transport Canada
        standard``.
    """
    return f"{AUTHORITY_NAMES[document.authority]} {TYPE_NAMES[document.type]}"


def attribution(document: DocumentSpec) -> str:
    """
    Write the attribution that must go with any quote from a document.

    The wording follows each source's terms in ``NOTICE.md``. The CARs are
    published by the Department of Justice Canada, so they are attributed
    to it rather than to Transport Canada.

    Args:
        document: The document's manifest entry.

    Returns:
        The full title, the publisher and the official URL, with what the
        source's terms ask to say about the copy.
    """
    title, url = document.title, document.official_url

    if document.authority == "FAA":
        return (
            f"{title}, Federal Aviation Administration. "
            f"The official version is at {url}."
        )

    if document.type == "regulation":
        return (
            f"{title}, Department of Justice Canada. "
            f"Not the official version; the official version is at {url}."
        )

    return (
        f"{title}, Transport Canada. A copy of the version available at {url}. "
        "Hangar is not affiliated with or endorsed by Transport Canada."
    )


def format_answer(
    answer: AnswerRecord, documents: Mapping[str, DocumentSpec], snapshot: str
) -> str:
    """
    Write an answer for the screen, with its sources and the study-aid notice.

    The answer comes first, then each citation in the order its marker first
    appears: a valid one with its document, pages or sections, label,
    content date and attribution; an invalid one flagged as such. An answer
    with no valid citation says so. The corpus snapshot and the study-aid
    notice close every answer.

    Args:
        answer: The answer record.
        documents: The manifest entry of each cited document, keyed by ID.
        snapshot: The corpus snapshot the answer was found in, such as
            ``c1``.

    Returns:
        The text to print.
    """
    lines = [answer.completion.text.strip(), "", "Sources:"]

    for citation in answer.citations:
        lines.extend(_describe_citation(citation, documents))

    if not any(citation.valid for citation in answer.citations):
        lines.append(
            "The answer cites no source, so nothing in it is backed by the documents."
        )

    lines.extend(["", f"Answered from corpus snapshot {snapshot}.", ""])
    lines.append(STUDY_AID_NOTICE)

    return "\n".join(lines)


def _describe_citation(
    citation: Citation, documents: Mapping[str, DocumentSpec]
) -> list[str]:
    marker = f"[{citation.marker}]"

    if not citation.valid or citation.document_id is None:
        return [f"{marker} invalid marker: no source has this number"]

    document = documents[citation.document_id]

    return [
        f"{marker} {document.id}, {describe_passages(citation.passages)}",
        f"    {source_label(document)}, content date {document.content_date}",
        f"    {attribution(document)}",
    ]
