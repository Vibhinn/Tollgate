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

    # "configured" only means the provider has an API key on file, not that it
    # currently works - a model whose provider just started failing (credits
    # exhausted, key revoked) stays out of consideration until its TTL clears,
    # instead of being recommended forever with no way to recover without a
    # human manually intervening.
    available_models = [
        model_name for model_name in configured_models
        if not await ranking_repo.is_unavailable(model_name)
    ]

    if not available_models:
        return None

    return min(
        available_models,
        key=lambda model_name: (PRICING_TABLE[model_name]["input"] + PRICING_TABLE[model_name]["output"]) / 2,
    )
