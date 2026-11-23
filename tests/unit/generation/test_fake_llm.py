import re

from hangar.core.prompts import Message
from hangar.generation.llm import FakeLlmClient

MESSAGES = (
    Message(role="system", content="Answer from the sources only."),
    Message(role="user", content="How often is the ELT battery replaced?"),
)


def test_the_fake_returns_its_canned_answer_with_citation_markers() -> None:
    completion = FakeLlmClient().complete(
        MESSAGES, temperature=0.0, max_output_tokens=512
    )

    assert re.search(r"\[1\]", completion.text)
    assert completion.model_id == "fake"
    assert completion.finish_reason == "stop"


def test_the_fake_can_return_a_chosen_answer() -> None:
    client = FakeLlmClient(answer="The sources don't cover this question.")

    completion = client.complete(MESSAGES, temperature=0.0, max_output_tokens=512)

    assert completion.text == "The sources don't cover this question."


def test_the_fake_counts_words_as_tokens() -> None:
    client = FakeLlmClient(answer="Replace it every year [1].")

    completion = client.complete(MESSAGES, temperature=0.0, max_output_tokens=512)

    # "Answer from the sources only." and "How often is the ELT battery
    # replaced?" have 5 and 7 words.
    assert completion.input_tokens == 12
    assert completion.output_tokens == 5
