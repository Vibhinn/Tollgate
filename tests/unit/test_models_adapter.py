from unittest.mock import MagicMock

from src.app.adapters import ModelsAdapter


def test_list_models_puts_the_policies_first_then_the_configured_models():
    router_manager = MagicMock()
    router_manager.available_models.return_value = {"gpt-4o": "openai", "claude-haiku-4-5": "anthropic"}

    models = ModelsAdapter(router_manager).list_models()

    assert list(models.items()) == [
        ("fast", "tollgate"), ("cheap", "tollgate"), ("smart", "tollgate"),
        ("gpt-4o", "openai"), ("claude-haiku-4-5", "anthropic"),
    ]


def test_list_models_offers_only_the_policies_when_no_provider_is_configured():
    router_manager = MagicMock()
    router_manager.available_models.return_value = {}

    assert list(ModelsAdapter(router_manager).list_models()) == ["fast", "cheap", "smart"]
