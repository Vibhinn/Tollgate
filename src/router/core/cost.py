from __future__ import annotations

from typing import TYPE_CHECKING

from src.utils.config import ROUTING_TABLE
from .pricing import PRICING_TABLE

if TYPE_CHECKING:
    from src.llm import LLMRepositoryFactory
    from src.app.ports import RankingRepositoryInterface


async def get_cheapest_model(llm_repo_factory: LLMRepositoryFactory, ranking_repo: RankingRepositoryInterface) -> str | None:
    configured_models = [
        model_name
        for model_name, entry in ROUTING_TABLE.items()
        if model_name in PRICING_TABLE and llm_repo_factory.get_repo(entry["provider"]) is not None
    ]

    available_models = await ranking_repo.filter_available(configured_models)

    if not available_models:
        return None

    return min(
        available_models,
        key=lambda model_name: (PRICING_TABLE[model_name]["input"] + PRICING_TABLE[model_name]["output"]) / 2,
    )
