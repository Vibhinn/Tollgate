from typing import TYPE_CHECKING

from src.utils.config import ROUTING_TABLE

if TYPE_CHECKING:
    from src.llm import LLMRepositoryFactory
    from src.app.ports import RankingRepositoryInterface

CATEGORY_MODEL_PREFERENCE = {
    "SIMPLE": ["claude-haiku-4-5", "gemini-3.5-flash-lite", "gpt-4o-mini"],
    "CODE": ["claude-sonnet-4-6", "gpt-4o", "gemini-3.5-flash"],
    "REASONING": ["claude-opus-4-6", "o1", "gpt-4o"],
    "CREATIVE": ["claude-opus-4-6", "gpt-4o", "gemini-3.5-flash"],
}


async def resolve_smart_model(
    category: str, llm_repo_factory: LLMRepositoryFactory, ranking_repo: RankingRepositoryInterface
) -> str | None:
    for model_name in CATEGORY_MODEL_PREFERENCE.get(category, []):
        entry = ROUTING_TABLE.get(model_name)
        if not entry:
            continue
        if llm_repo_factory.get_repo(entry["provider"]) is None:
            continue
        if await ranking_repo.is_unavailable(model_name):
            continue
        return model_name
    return None
