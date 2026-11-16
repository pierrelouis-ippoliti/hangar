"""
The token counter for Hugging Face models, such as BGE-M3.

It reads the model's ``tokenizer.json`` with the ``tokenizers`` library, at
the revision pinned in the configuration, so chunks are counted in the same
tokens the embedder sees.
"""

from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer


class HfTokenCounter:
    """
    Counts tokens with a Hugging Face tokenizer, without its special tokens.

    BGE-M3 adds ``<s>`` and ``</s>`` around every text, so a chunk of 512
    tokens reaches the model as 514. The model accepts 8,192, so nothing is
    cut off.
    """

    def __init__(self, tokenizer: Tokenizer) -> None:
        """
        Wrap a tokenizer.

        Args:
            tokenizer: The tokenizer. Its truncation and padding are turned
                off, since truncation would silently drop the end of a long
                document.
        """
        tokenizer.no_truncation()
        tokenizer.no_padding()
        self._tokenizer = tokenizer

    @classmethod
    def from_hub(cls, model: str, revision: str) -> "HfTokenCounter":
        """
        Load a model's tokenizer from Hugging Face, or from the local cache.

        Args:
            model: The Hugging Face model ID, such as ``BAAI/bge-m3``.
            revision: The model's commit hash.

        Returns:
            The token counter for that model.
        """
        path = hf_hub_download(model, "tokenizer.json", revision=revision)

        return cls(Tokenizer.from_file(path))

    def count(self, text: str) -> int:
        """
        Count the tokens of a text, without the special tokens.

        Args:
            text: The text to count.

        Returns:
            The number of tokens.
        """
        return len(self._tokenizer.encode(text, add_special_tokens=False).ids)

    def token_starts(self, text: str) -> list[int]:
        """
        Find where each token of a text starts.

        Args:
            text: The text to split into tokens.

        Returns:
            The character offset of each token's first character, without
            the special tokens.
        """
        encoding = self._tokenizer.encode(text, add_special_tokens=False)

        return [start for start, _ in encoding.offsets]
