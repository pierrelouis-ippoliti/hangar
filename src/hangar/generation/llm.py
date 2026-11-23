"""
The language model client interface, and a fake client for tests.

A client sends the rendered messages to a model and returns its completion.
The Mistral adapter (``generation.mistral``) is the real one; v9 adds a
client for a self-hosted copy of the same model.
"""

from collections.abc import Sequence
from typing import Protocol

from hangar.core.completions import Completion
from hangar.core.errors import HangarError
from hangar.core.prompts import Message

FAKE_ANSWER = (
    "Replace the ELT battery when half its useful life has passed [1]. "
    "Record the replacement date on the outside of the transmitter [2]."
)


class LlmError(HangarError):
    """A completion the language model client couldn't get."""


class LlmClient(Protocol):
    """
    Sends messages to a language model and returns its completion.

    Attributes:
        model_id: The model the client asks for, such as
            ``mistral-small-2603``.
    """

    model_id: str

    def complete(
        self,
        messages: Sequence[Message],
        *,
        temperature: float,
        max_output_tokens: int,
    ) -> Completion:
        """
        Ask the model to answer the messages.

        Args:
            messages: The messages to send, in order.
            temperature: The sampling temperature. 0 picks the most likely
                token each time.
            max_output_tokens: The most tokens the answer may use.

        Returns:
            The model's completion.

        Raises:
            LlmError: If no completion could be obtained.
        """
        ...


class FakeLlmClient:
    """
    Returns the same answer to every prompt, without calling a model. For tests.

    The default answer cites sources [1] and [2], so tests of the citation
    parser and the answer pipeline get markers to work with. Tokens are
    counted as words separated by spaces, which is enough to test totals and
    costs.

    Attributes:
        model_id: Always ``fake``.
    """

    def __init__(self, answer: str = FAKE_ANSWER) -> None:
        """
        Set up the client.

        Args:
            answer: The text every completion returns.
        """
        self.model_id = "fake"
        self._answer = answer

    def complete(
        self,
        messages: Sequence[Message],
        *,
        temperature: float,
        max_output_tokens: int,
    ) -> Completion:
        """
        Return the canned answer.

        Args:
            messages: The messages, used only to count input tokens.
            temperature: Ignored.
            max_output_tokens: Ignored.

        Returns:
            The canned answer, with ``stop`` as its finish reason and no
            latency.
        """
        input_words = sum(len(message.content.split()) for message in messages)

        return Completion(
            text=self._answer,
            model_id=self.model_id,
            input_tokens=input_words,
            output_tokens=len(self._answer.split()),
            latency_seconds=0.0,
            finish_reason="stop",
        )
