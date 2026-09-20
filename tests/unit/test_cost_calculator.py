from unittest.mock import MagicMock

from src.router.core.cost import get_cheapest_model


def make_factory(configured_providers):
    factory = MagicMock()
    factory.get_repo = lambda provider: object() if provider in configured_providers else None
    return factory


def test_picks_cheapest_by_average_of_input_and_output_price():
    factory = make_factory({"openai", "anthropic", "gemini"})

    result = get_cheapest_model(factory)

    # gemini-2.0-flash-lite: (0.075 + 0.30) / 2 = 0.1875, cheapest in PRICING_TABLE
    assert result == "gemini-2.0-flash-lite"


def test_only_considers_configured_providers():
    factory = make_factory({"anthropic"})

    result = get_cheapest_model(factory)

    # cheapest Anthropic model by (input+output)/2 is claude-haiku-4-5: (1.00+5.00)/2 = 3.0
    assert result == "claude-haiku-4-5"


def test_returns_none_when_no_provider_is_configured():
    factory = make_factory(set())

    result = get_cheapest_model(factory)

    assert result is None
