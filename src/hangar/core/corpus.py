"""
The corpus manifest: which documents a snapshot holds, and where they come from.

The manifest is written by hand. Each entry says where to download a
document and the SHA-256 it must have. This module validates the manifest's
content; reading the file is the ``corpus`` package's job. It also defines
the record of a downloaded file, the raw artifact.
"""

import datetime
from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    NonNegativeInt,
    ValidationError,
    field_validator,
)

from hangar.core.errors import ConfigError, FieldProblem, field_problems

Authority = Literal["FAA", "TC"]
DocumentType = Literal["handbook", "regulation", "standard", "advisory_circular"]
DocumentFormat = Literal["pdf", "xml", "html"]
DocumentStatus = Literal["active", "cancelled"]

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class DocumentSpec(BaseModel):
    """
    One document of the manifest, as written by hand.

    Attributes:
        id: A readable slug of lowercase letters and digits joined by
            hyphens, such as ``faa-h-8083-31b`` or ``tc-ac-571-025``.
        title: The document's title.
        authority: Who publishes it: the FAA or Transport Canada (TC).
        type: What kind of document it is.
        language: The language of the text, as a two-letter code such as
            ``en``.
        source_url: Where the document is downloaded from.
        format: The file format, which decides the parser.
        edition: The edition or revision, such as ``B`` or ``2023``.
        content_date: When the content itself was issued or consolidated.
        page_modified_date: When the page or file was last modified. It
            can be much later than the content date: Standard 571's page
            was modified in 2024, but its content dates from 2010.
        retrieved_on: When the document was downloaded to compute its hash.
        status: Whether the document is in force. Cancelled documents stay
            out of a snapshot.
        sha256: The SHA-256 the downloaded file must have, as 64 lowercase
            hex characters.
        reuse_note: The terms under which the document may be reused.
    """

    # YAML reads `edition: 2023` as a number; keep it as text.
    model_config = ConfigDict(frozen=True, extra="forbid", coerce_numbers_to_str=True)

    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    title: str = Field(min_length=1)
    authority: Authority
    type: DocumentType
    language: str = Field(pattern=r"^[a-z]{2}$")
    source_url: HttpUrl
    format: DocumentFormat
    edition: str = Field(min_length=1)
    content_date: datetime.date
    page_modified_date: datetime.date
    retrieved_on: datetime.date
    status: DocumentStatus
    sha256: str = Field(pattern=SHA256_PATTERN)
    reuse_note: str = Field(min_length=1)


class Manifest(BaseModel):
    """
    The corpus manifest: a snapshot and its documents.

    Attributes:
        snapshot: The snapshot the manifest describes, such as ``c1``.
        documents: Every document, in the order the file lists them,
            cancelled ones included.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot: str = Field(pattern=r"^c[0-9]+$")
    documents: tuple[DocumentSpec, ...]

    # A length constraint on a tuple field would also fail whenever an entry
    # is invalid, adding a misleading second error. An after-validator runs
    # only once every entry is valid.
    @field_validator("documents")
    @classmethod
    def _check_not_empty(
        cls, documents: tuple[DocumentSpec, ...]
    ) -> tuple[DocumentSpec, ...]:
        if not documents:
            raise ValueError("the manifest must list at least one document")

        return documents

    def active_documents(self) -> tuple[DocumentSpec, ...]:
        """
        List the documents that are in force.

        Returns:
            The documents whose status is not cancelled, in manifest order.
        """
        return tuple(d for d in self.documents if d.status != "cancelled")


def parse_manifest(data: object, source: str) -> Manifest:
    """
    Validate the content of a manifest file.

    Args:
        data: The file's content, as read from YAML.
        source: The file the content came from, used in error messages.

    Returns:
        The validated manifest.

    Raises:
        ConfigError: If the content is not a valid manifest or two
            documents share an ID. The error lists every problem, each
            with its field, such as ``documents[2].sha256``.
    """
    if not isinstance(data, dict):
        raise ConfigError(
            source,
            [
                FieldProblem(
                    None, "the file must be a mapping with a snapshot and documents"
                )
            ],
        )

    try:
        manifest = Manifest.model_validate(data)
    except ValidationError as error:
        raise ConfigError(source, field_problems(error)) from error

    duplicates = _duplicate_ids(manifest.documents)

    if duplicates:
        raise ConfigError(source, duplicates)

    return manifest


def _duplicate_ids(documents: tuple[DocumentSpec, ...]) -> list[FieldProblem]:
    first_position: dict[str, int] = {}
    problems = []

    for position, spec in enumerate(documents):
        if spec.id in first_position:
            problems.append(
                FieldProblem(
                    f"documents[{position}].id",
                    f"duplicate ID {spec.id!r}, "
                    f"already used by documents[{first_position[spec.id]}]",
                )
            )
        else:
            first_position[spec.id] = position

    return problems


def raw_artifact_id(spec: DocumentSpec) -> str:
    """
    Give the ID of a document's downloaded file, which is also its file name.

    Args:
        spec: The document.

    Returns:
        The document ID followed by its format as the extension, such as
        ``faa-h-8083-31b.pdf``.
    """
    return f"{spec.id}.{spec.format}"


class RawArtifact(BaseModel):
    """
    One downloaded document file, as recorded in the fetch log.

    Attributes:
        id: The file's ID, from ``raw_artifact_id``, such as
            ``faa-h-8083-31b.pdf``.
        document_id: The manifest ID of the document.
        path: Where the file was written.
        sha256: The file's SHA-256, as 64 lowercase hex characters.
        size_bytes: The file's size.
        fetched_at: When the download finished, with its time zone.
        etag: The server's ``ETag`` header, or None if it sent none.
        last_modified: The server's ``Last-Modified`` header, as sent, or
            None if it sent none.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=SHA256_PATTERN)
    size_bytes: NonNegativeInt
    fetched_at: AwareDatetime
    etag: str | None
    last_modified: str | None
