"""
The prompt renderer: a prompt file, a question and its chunks in; messages out.

A prompt file, such as ``prompts/answer-v0.md``, has three parts, each
starting with a level-1 heading on its own line:

- ``# System``: the instructions, sent as the system message.
- ``# User``: the user message, with ``$question`` and ``$sources``.
- ``# Source``: how one source is written into ``$sources``.

The placeholders follow Python's ``string.Template``, so a literal dollar
sign is written ``$$``. Prompt files are never edited in place: a new
version of the prompt is a new file.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from string import Template

from hangar.core.chunks import Chunk, describe_passages
from hangar.core.corpus import DocumentSpec
from hangar.core.errors import HangarError
from hangar.core.prompts import Message, RenderedPrompt, Source
from hangar.core.retrieval import ScoredChunk
from hangar.generation.presentation import source_label

PART_NAMES = ("System", "User", "Source")
PART_HEADINGS = {f"# {name}": name for name in PART_NAMES}

# The placeholders each part must use, all of them and no others.
PLACEHOLDERS = {
    "System": frozenset[str](),
    "User": frozenset({"question", "sources"}),
    "Source": frozenset({"number", "label", "title", "date", "location", "text"}),
}


class PromptError(HangarError):
    """
    A prompt that can't be rendered.

    Either the prompt file is broken, or a chunk's document is missing from
    the manifest.
    """


@dataclass(frozen=True)
class PromptTemplate:
    """
    A prompt file, split into its three parts.

    Attributes:
        version: The prompt version, the file name without ``.md``.
        system: The instructions.
        user: The user message.
        source: How one source is written.
    """

    version: str
    system: Template
    user: Template
    source: Template

    def render(
        self,
        question: str,
        results: Sequence[ScoredChunk],
        documents: Mapping[str, DocumentSpec],
    ) -> RenderedPrompt:
        """
        Write the messages for a question and the chunks found for it.

        Args:
            question: The question, in plain words.
            results: The chunks found, best first.
            documents: The manifest entry of each document, keyed by ID.

        Returns:
            The messages, and the source map that numbers the chunks from 1
            in the order given.

        Raises:
            PromptError: If a chunk's document is not in ``documents``.
        """
        sources = []
        blocks = []

        for number, result in enumerate(results, start=1):
            chunk = result.chunk
            sources.append(
                Source(
                    number=number,
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    passages=chunk.passages,
                )
            )
            blocks.append(self._write_source(number, chunk, documents))

        user = self.user.substitute(question=question, sources="\n\n".join(blocks))

        return RenderedPrompt(
            prompt_version=self.version,
            messages=(
                Message(role="system", content=self.system.substitute()),
                Message(role="user", content=user),
            ),
            sources=tuple(sources),
        )

    def _write_source(
        self,
        number: int,
        chunk: Chunk,
        documents: Mapping[str, DocumentSpec],
    ) -> str:
        document = documents.get(chunk.document_id)

        if document is None:
            raise PromptError(
                f"chunk {chunk.id} comes from {chunk.document_id}, "
                "which is not in the manifest"
            )

        return self.source.substitute(
            number=number,
            label=source_label(document),
            title=document.title,
            date=document.content_date.isoformat(),
            location=describe_passages(chunk.passages),
            text=chunk.text,
        )


def load_prompt_template(folder: Path, version: str) -> PromptTemplate:
    """
    Read a prompt file and check its parts.

    Args:
        folder: The folder of prompt files, ``prompts/`` in the repository.
        version: The prompt version, such as ``answer-v0``.

    Returns:
        The prompt template.

    Raises:
        PromptError: If the file can't be read, or if it doesn't have each
            part exactly once, each with its own placeholders and nothing
            else. The error names the file.
    """
    path = folder / f"{version}.md"

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise PromptError(f"{path}: can't read the file: {error.strerror}") from error

    try:
        parts = _split_parts(text)
        templates = {name: _check_part(name, parts[name]) for name in PART_NAMES}
    except ValueError as error:
        raise PromptError(f"{path}: {error}") from error

    return PromptTemplate(
        version=version,
        system=templates["System"],
        user=templates["User"],
        source=templates["Source"],
    )


def _split_parts(text: str) -> dict[str, str]:
    parts: dict[str, list[str]] = {}
    current: list[str] | None = None

    for line in text.splitlines():
        name = PART_HEADINGS.get(line.rstrip())

        if name is not None:
            if name in parts:
                raise ValueError(f"two '# {name}' parts")

            current = parts[name] = []
        elif current is not None:
            current.append(line)
        elif line.strip():
            raise ValueError("text before the first part, such as '# System'")

    for name in PART_NAMES:
        if name not in parts:
            raise ValueError(f"no '# {name}' part")

    return {name: "\n".join(lines).strip() for name, lines in parts.items()}


def _check_part(name: str, body: str) -> Template:
    if not body:
        raise ValueError(f"'# {name}' is empty")

    template = Template(body)

    if not template.is_valid():
        raise ValueError(
            f"'# {name}' has a $ that starts no placeholder; "
            "write a literal dollar sign as $$"
        )

    used = set(template.get_identifiers())
    expected = PLACEHOLDERS[name]
    unknown = sorted(used - expected)
    missing = sorted(expected - used)

    if unknown:
        raise ValueError(f"'# {name}' has unknown {_format_placeholders(unknown)}")

    if missing:
        raise ValueError(f"'# {name}' is missing {_format_placeholders(missing)}")

    return template


def _format_placeholders(names: list[str]) -> str:
    return ", ".join(f"${name}" for name in names)
