from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from src.utils.types import LLMInvocationResult, last_user_message
from src.app.exceptions import ModelSemanticNotFound, NoHealthyModelAvailable

if TYPE_CHECKING:
    from src.router import RouterRepository
    from src.cache import ResponseCache
    from src.utils.types import Message, GenerationParams, ChatRequest

class ChatAdapter:
    def __init__(self, response_cache: ResponseCache, router_manager: RouterRepository):
        self.response_cache = response_cache
        self.router_repo = router_manager
        self._MODEL_SELECTION_POLICIES = ("fast", "cheap", "smart")

    async def complete(self, user_id: str | None, chat_request: ChatRequest) -> LLMInvocationResult:
        self.ensure_model_exists(chat_request.model)
        cache_keys = self.response_cache.build_keys(user_id, chat_request)

        cached_answer, cache_outcome = await self.response_cache.lookup(cache_keys, chat_request.cache_match_score)
        if cached_answer:
            return LLMInvocationResult(content=cached_answer, input_tokens=0, output_tokens=0,
                                       model=chat_request.model, cache_outcome=cache_outcome)

        result = await self.query_llm(chat_request.model, chat_request.messages, chat_request.params)

        if chat_request.cache_type and result.finish_reason == "stop":
            await self.response_cache.store(cache_keys, result.content, chat_request.cache_type, chat_request.cache_ttl)
        return replace(result, cache_outcome=cache_outcome)

    def ensure_model_exists(self, model_name: str) -> None:
        if model_name not in self._MODEL_SELECTION_POLICIES and not self.router_repo.has_model(model_name):
            raise ModelSemanticNotFound(f"The model '{model_name}' does not exist. GET /v1/models lists the available ones.")

    async def query_llm(self, model_name: str, messages: list[Message], params: GenerationParams) -> LLMInvocationResult:
        if model_name in self._MODEL_SELECTION_POLICIES:
            recommended_model = await self.router_repo.get_best_model(
                model_name,
                user_message=last_user_message(messages) if model_name == "smart" else None
            )
            if recommended_model is None:
                await self._raise_no_model_for(model_name)
            return await self.router_repo.invoke_model(model_name=recommended_model, messages=messages, params=params,
                                                       model_selection_policy=model_name)
        else:
            return await self.router_repo.invoke_model(model_name=model_name, messages=messages, params=params)

    async def _raise_no_model_for(self, policy: str) -> None:
        # benched models come back on their own, so that's a 503 worth retrying; with nothing benched,
        # waiting won't help (e.g. no model for this kind of prompt is configured), so it stays a 404
        retry_after = await self.router_repo.seconds_until_a_model_returns()
        if retry_after is not None:
            raise NoHealthyModelAvailable(
                f"Every model the '{policy}' policy could use is temporarily out of rotation after provider errors. "
                f"Retry in {retry_after}s.", retry_after)
        raise ModelSemanticNotFound(f"No configured model is available for the '{policy}' policy.")
