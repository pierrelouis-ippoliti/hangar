"""
Completions: what the language model wrote, and what it cost to write it.

The answer record (#27) keeps the completion of each answer, so its token
counts and latency can be totalled and priced.
"""

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
)


class Completion(BaseModel):
    """
    The language model's reply to one prompt.

    Attributes:
        text: The answer the model wrote.
        model_id: The model that wrote it, as the provider reports it,
            such as ``mistral-small-2603``.
        input_tokens: How many tokens the prompt used.
        output_tokens: How many tokens the answer used.
        latency_seconds: How long the request that returned the answer
            took. Waits for the rate limit and failed attempts are not
            included.
        finish_reason: Why the model stopped, as the provider reports it,
            such as ``stop`` for a finished answer or ``length`` for one
            cut off at the token limit.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    model_id: str = Field(min_length=1)
    input_tokens: NonNegativeInt
    output_tokens: NonNegativeInt
    latency_seconds: NonNegativeFloat
    finish_reason: str = Field(min_length=1)
