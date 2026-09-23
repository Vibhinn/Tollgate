from unittest.mock import AsyncMock, MagicMock

from src.router.core.cost import get_cheapest_model


def make_factory(configured_providers):
    factory = MagicMock()
    factory.get_repo = lambda provider: object() if provider in configured_providers else None
    return factory


def make_ranking_repo(unavailable=frozenset()):
    ranking_repo = AsyncMock()
    ranking_repo.is_unavailable.side_effect = lambda model_name: model_name in unavailable
    return ranking_repo


async def test_picks_cheapest_by_average_of_input_and_output_price():
    factory = make_factory({"openai", "anthropic", "gemini"})

    result = await get_cheapest_model(factory, make_ranking_repo())

    # gemini-3.5-flash-lite: (0.075 + 0.30) / 2 = 0.1875, cheapest in PRICING_TABLE
    assert result == "gemini-3.5-flash-lite"


async def test_only_considers_configured_providers():
    factory = make_factory({"anthropic"})

    result = await get_cheapest_model(factory, make_ranking_repo())

    # cheapest Anthropic model by (input+output)/2 is claude-haiku-4-5: (1.00+5.00)/2 = 3.0
    assert result == "claude-haiku-4-5"


async def test_returns_none_when_no_provider_is_configured():
    factory = make_factory(set())

    result = await get_cheapest_model(factory, make_ranking_repo())

    assert result is None


async def test_excludes_models_marked_unavailable():
    factory = make_factory({"openai", "anthropic", "gemini"})

    result = await get_cheapest_model(factory, make_ranking_repo(unavailable={"gemini-3.5-flash-lite"}))

    # next cheapest after gemini-3.5-flash-lite is excluded: gemini-3.5-flash (0.10+0.40)/2 = 0.25
    assert result == "gemini-3.5-flash"


async def test_returns_none_when_every_configured_model_is_unavailable():
    factory = make_factory({"gemini"})
    all_gemini = {"gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.5-pro"}

    result = await get_cheapest_model(factory, make_ranking_repo(unavailable=all_gemini))

    assert result is None
