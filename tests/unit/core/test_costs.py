import pytest

from hangar.core.config import ModelPrices, TokenPrice
from hangar.core.costs import Cost, token_cost, total_cost

# The v0 prices of mistral-small-2603: free, or 0.15 and 0.60 US dollars per
# million input and output tokens at list price.
V0_PRICES = ModelPrices(
    free_tier=TokenPrice(input_usd_per_million=0.0, output_usd_per_million=0.0),
    list_price=TokenPrice(input_usd_per_million=0.15, output_usd_per_million=0.6),
)


def test_a_million_tokens_cost_the_price_per_million() -> None:
    assert token_cost(V0_PRICES, 1_000_000, 0).list_price_usd == pytest.approx(0.15)
    assert token_cost(V0_PRICES, 0, 1_000_000).list_price_usd == pytest.approx(0.6)


def test_input_and_output_tokens_are_priced_separately_and_added() -> None:
    # 2,000 x 0.15 / 1e6 = 0.0003, plus 500 x 0.60 / 1e6 = 0.0003.
    cost = token_cost(V0_PRICES, 2_000, 500)

    assert cost.list_price_usd == pytest.approx(0.0006)


def test_the_free_tier_costs_nothing() -> None:
    assert token_cost(V0_PRICES, 2_000, 500).free_tier_usd == 0.0


def test_no_tokens_cost_nothing() -> None:
    assert token_cost(V0_PRICES, 0, 0) == Cost(free_tier_usd=0.0, list_price_usd=0.0)


def test_both_tiers_are_priced_from_their_own_table() -> None:
    prices = ModelPrices(
        free_tier=TokenPrice(input_usd_per_million=1.0, output_usd_per_million=2.0),
        list_price=TokenPrice(input_usd_per_million=3.0, output_usd_per_million=4.0),
    )

    cost = token_cost(prices, 1_000_000, 1_000_000)

    assert cost.free_tier_usd == pytest.approx(3.0)
    assert cost.list_price_usd == pytest.approx(7.0)


def test_a_total_adds_each_tier_separately() -> None:
    total = total_cost(
        [
            Cost(free_tier_usd=0.5, list_price_usd=1.0),
            Cost(free_tier_usd=0.25, list_price_usd=2.0),
        ]
    )

    assert total.free_tier_usd == pytest.approx(0.75)
    assert total.list_price_usd == pytest.approx(3.0)


def test_the_total_of_no_costs_is_zero() -> None:
    assert total_cost([]) == Cost(free_tier_usd=0.0, list_price_usd=0.0)
