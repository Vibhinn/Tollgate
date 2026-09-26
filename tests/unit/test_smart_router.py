from unittest.mock import AsyncMock, MagicMock

from src.router.core.smart import resolve_smart_model


def make_factory(configured_providers):
    factory = MagicMock()
    factory.get_repo = lambda provider: object() if provider in configured_providers else None
    return factory


def make_ranking_repo(unavailable=frozenset()):
    ranking_repo = AsyncMock()
    ranking_repo.is_unavailable.side_effect = lambda model_name: model_name in unavailable
    return ranking_repo


async def test_resolves_to_the_first_preference_when_everything_is_configured():
    factory = make_factory({"anthropic", "openai", "gemini"})

    result = await resolve_smart_model("REASONING", factory, make_ranking_repo())

    assert result == "claude-opus-4-6"


async def test_skips_preferences_whose_provider_is_not_configured():
    factory = make_factory({"openai"})

    result = await resolve_smart_model("REASONING", factory, make_ranking_repo())

    assert result == "o1"


async def test_skips_preferences_that_are_currently_blocklisted():
    factory = make_factory({"anthropic", "openai"})

    result = await resolve_smart_model("REASONING", factory, make_ranking_repo(unavailable={"claude-opus-4-6"}))

    assert result == "o1"


async def test_returns_none_when_nothing_in_the_category_is_available():
    factory = make_factory(set())

    result = await resolve_smart_model("REASONING", factory, make_ranking_repo())

    assert result is None


async def test_returns_none_for_an_unknown_category():
    factory = make_factory({"anthropic", "openai", "gemini"})

    result = await resolve_smart_model("NOT_A_REAL_CATEGORY", factory, make_ranking_repo())

    assert result is None


async def test_each_category_has_at_least_one_preference_configured_end_to_end():
    """Every category should resolve to something when all providers are
    configured and nothing is blocklisted - catches a typo'd model name in
    the preference table that would silently make a whole category dead."""
    from src.router.core.smart import CATEGORY_MODEL_PREFERENCE

    factory = make_factory({"anthropic", "openai", "gemini"})

    for category in CATEGORY_MODEL_PREFERENCE:
        result = await resolve_smart_model(category, factory, make_ranking_repo())
        assert result is not None, f"category {category!r} resolved to nothing"
