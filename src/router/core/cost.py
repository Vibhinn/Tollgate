from typing import TYPE_CHECKING

from src.utils.config import ROUTING_TABLE
from .pricing import PRICING_TABLE

if TYPE_CHECKING:
    from src.llm import LLMRepositoryFactory


def get_cheapest_model(llm_repo_factory: LLMRepositoryFactory) -> str | None:
    configured_models = [
        model_name
        for model_name, entry in ROUTING_TABLE.items()
        if model_name in PRICING_TABLE and llm_repo_factory.get_repo(entry["provider"]) is not None
    ]

    if not configured_models:
        return None

    return min(
        configured_models,
        key=lambda model_name: (PRICING_TABLE[model_name]["input"] + PRICING_TABLE[model_name]["output"]) / 2,
    )
