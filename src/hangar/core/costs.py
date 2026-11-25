"""
Costs: what the language model's tokens cost, priced from the configuration.

v0 runs on Mistral's free tier, so what it pays is zero. Each cost also
says what the same tokens would cost at list price, which v9 compares with
the cost of a self-hosted model.
"""

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, NonNegativeFloat

from hangar.core.config import ModelPrices, TokenPrice

TOKENS_PER_PRICE_UNIT = 1_000_000


class Cost(BaseModel):
    """
    What some tokens cost, in US dollars, at both prices of the configuration.

    Attributes:
        free_tier_usd: The cost on the free tier, which v0 uses.
        list_price_usd: The cost of the same tokens at the published price.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    free_tier_usd: NonNegativeFloat
    list_price_usd: NonNegativeFloat


def token_cost(prices: ModelPrices, input_tokens: int, output_tokens: int) -> Cost:
    """
    Price a model's input and output tokens.

    Args:
        prices: The model's prices from the configuration, per million
            tokens.
        input_tokens: How many tokens the prompts used.
        output_tokens: How many tokens the answers used.

    Returns:
        The cost on the free tier and at list price.
    """
    return Cost(
        free_tier_usd=_price(prices.free_tier, input_tokens, output_tokens),
        list_price_usd=_price(prices.list_price, input_tokens, output_tokens),
    )


def total_cost(costs: Iterable[Cost]) -> Cost:
    """
    Add costs up, each price separately.

    Args:
        costs: The costs to add, such as one per answer of a run.

    Returns:
        The total on the free tier and at list price; zero for no costs.
    """
    costs = list(costs)

    return Cost(
        free_tier_usd=sum(cost.free_tier_usd for cost in costs),
        list_price_usd=sum(cost.list_price_usd for cost in costs),
    )


def _price(price: TokenPrice, input_tokens: int, output_tokens: int) -> float:
    usd = (
        input_tokens * price.input_usd_per_million
        + output_tokens * price.output_usd_per_million
    )

    return usd / TOKENS_PER_PRICE_UNIT
