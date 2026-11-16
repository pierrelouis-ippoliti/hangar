from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace
from tokenizers.processors import TemplateProcessing

from hangar.chunking.hf_tokenizer import HfTokenCounter

VOCAB = {"[UNK]": 0, "<s>": 1, "</s>": 2, "torque": 3, "the": 4, "bolt": 5}


def tiny_tokenizer() -> Tokenizer:
    """A word tokenizer that adds <s> and </s>, and truncates to 2 tokens."""
    tokenizer = Tokenizer(WordLevel(VOCAB, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = Whitespace()
    tokenizer.post_processor = TemplateProcessing(
        single="<s> $A </s>", special_tokens=[("<s>", 1), ("</s>", 2)]
    )
    tokenizer.enable_truncation(max_length=2)

    return tokenizer


def test_count_leaves_out_the_special_tokens() -> None:
    counter = HfTokenCounter(tiny_tokenizer())

    assert counter.count("torque the bolt") == 3


def test_token_starts_are_character_offsets() -> None:
    counter = HfTokenCounter(tiny_tokenizer())

    assert counter.token_starts("torque  the bolt") == [0, 8, 12]


def test_long_texts_are_never_truncated() -> None:
    counter = HfTokenCounter(tiny_tokenizer())
    text = " ".join(["bolt"] * 1000)

    assert counter.count(text) == 1000
    assert len(counter.token_starts(text)) == 1000
