"""
The token counter interface, and a word counter for tests.

v0 counts tokens with BGE-M3's tokenizer (``hf_tokenizer``). Tests use the
whitespace counter instead, which needs no model.
"""

import re
from typing import Protocol

_WORD = re.compile(r"\S+")


class TokenCounter(Protocol):
    """
    Counts tokens the way an embedder sees them, and finds where they start.
    """

    def count(self, text: str) -> int:
        """
        Count the tokens of a text, without the special tokens a model adds.

        Args:
            text: The text to count.

        Returns:
            The number of tokens.
        """
        ...

    def token_starts(self, text: str) -> list[int]:
        """
        Find where each token of a text starts.

        Args:
            text: The text to split into tokens.

        Returns:
            The character offset of each token's first character, in
            increasing order, without the special tokens a model adds. A
            token may include the whitespace before it, as BGE-M3's do.
        """
        ...


class WhitespaceCounter:
    """
    Counts each run of non-space characters as one token. For tests.
    """

    def count(self, text: str) -> int:
        """
        Count the words of a text.

        Args:
            text: The text to count.

        Returns:
            The number of runs of non-space characters.
        """
        return len(_WORD.findall(text))

    def token_starts(self, text: str) -> list[int]:
        """
        Find where each word of a text starts.

        Args:
            text: The text to split into words.

        Returns:
            The offset of the first character of each run of non-space
            characters.
        """
        return [match.start() for match in _WORD.finditer(text)]
