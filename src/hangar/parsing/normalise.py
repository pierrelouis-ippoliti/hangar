"""
Text normalisation: the clean-up every parser applies to extracted text.
"""

import re
import unicodedata

from hangar.core.config import NormalisationConfig

_SPACES_AND_TABS = re.compile(r"[ \t]+")


def normalise(text: str, config: NormalisationConfig) -> str:
    """
    Clean up extracted text before it becomes part of a canonical text.

    The Unicode form comes first, because it can turn characters such as
    non-breaking spaces into plain spaces. Windows and old Mac line endings
    always become plain newlines, so every canonical text uses one kind.
    Newlines are never removed: they keep paragraphs and list items apart.

    Args:
        text: The text as the parser extracted it.
        config: The Unicode form, and whether runs of spaces and tabs become
            one space.

    Returns:
        The normalised text.
    """
    text = unicodedata.normalize(config.unicode_form, text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    if config.collapse_whitespace:
        text = _SPACES_AND_TABS.sub(" ", text)

    return text
