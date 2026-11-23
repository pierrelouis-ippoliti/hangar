"""
Rendered prompts: the messages sent to the language model, and their sources.

The prompt renderer numbers the retrieved chunks [1], [2] and so on, and
the answer cites them by those numbers. The source map keeps what each
number stands for, so a citation can be traced back to a document and its
pages or sections.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from hangar.core.chunks import CHUNK_ID_LENGTH, PassageRef
from hangar.core.corpus import DOCUMENT_ID_PATTERN


class PromptModel(BaseModel):
    """
    A part of a rendered prompt: frozen, and with no unknown fields.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class Message(PromptModel):
    """
    One message sent to the language model.

    Attributes:
        role: Who speaks: ``system`` for the instructions, ``user`` for the
            question and its sources.
        content: The message text.
    """

    role: Literal["system", "user"]
    content: str = Field(min_length=1)


class Source(PromptModel):
    """
    One numbered source of a prompt: a retrieved chunk.

    Attributes:
        number: The number the answer cites it by, such as 2 for ``[2]``.
        chunk_id: The chunk's ID.
        document_id: The manifest ID of the chunk's document.
        passages: The pages or sections the chunk covers, in text order.
    """

    number: PositiveInt
    chunk_id: str = Field(pattern=rf"^[0-9a-f]{{{CHUNK_ID_LENGTH}}}$")
    document_id: str = Field(pattern=DOCUMENT_ID_PATTERN)
    passages: tuple[PassageRef, ...] = Field(min_length=1)


class RenderedPrompt(PromptModel):
    """
    A prompt ready for the language model, with its source map.

    Attributes:
        prompt_version: The prompt file it was rendered from, such as
            ``answer-v0``.
        messages: The messages to send, in order.
        sources: The source map: one source per chunk in the prompt,
            numbered from 1 in the order they appear.
    """

    prompt_version: str = Field(min_length=1)
    messages: tuple[Message, ...] = Field(min_length=1)
    sources: tuple[Source, ...]
