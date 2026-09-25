import time
from datetime import datetime
from typing import TYPE_CHECKING

from src.app.exceptions import (
    ModelSemanticNotFound, APIKeyInvalidOrExpired, CreditExhaustion,
    PermissionDeniedForModel, RateLimitedFromModelProvider, ModelProviderServerError,
)
from src.utils.types import AnalyticsJobData, RedisStreamName, ConfigurationSection, ConfigurationOption
from src.utils.config import ROUTING_TABLE
from src.llm import LLMRepositoryFactory

from src.app.adapters import RouterAdapter

if TYPE_CHECKING:
    from src.utils.types import Message
    from src.utils.config import Config


class RouterRepository:
    def __init__(self, llm_repo_factory: LLMRepositoryFactory, router_adapter: RouterAdapter, config: Config):
        self.routing_table = ROUTING_TABLE
        self.llm_repo_factory = llm_repo_factory
        self.router_adapter = router_adapter
        self.config = config
        self._TTL_BY_EXCEPTION_MAP = {
                                        APIKeyInvalidOrExpired: 600,
                                        CreditExhaustion: 600,
                                        PermissionDeniedForModel: 600,
                                        RateLimitedFromModelProvider: 30,
                                        ModelProviderServerError: 30,
                                    }

    async def invoke_model(self, model_name: str, messages: list[Message], max_tokens: int, model_selection_policy: str | None = None) -> str:
        model_entry = self.routing_table.get(model_name)
        if not model_entry:
            raise ModelSemanticNotFound(f"Sorry, no such model found: {model_name}")

        model_provider_name: str = model_entry.get("provider")
        repository = self.llm_repo_factory.get_repo(model_provider_name)

        if not repository:
            raise ModelSemanticNotFound("Sorry, the provider is not supported by Tollgate at this moment. Please retry with a new one")

        real_model_name: str = model_entry.get("model", model_name)

        try:
            start: float = time.monotonic()
            model_response = await repository.invoke(messages[-1].content, real_model_name, max_tokens)
            latency_ms: float = (time.monotonic() - start)*1000
        except tuple(self._TTL_BY_EXCEPTION_MAP) as e:
            ttl: int = self._TTL_BY_EXCEPTION_MAP[type(e)]
            await self.router_adapter.mark_model_unavailable(model_name, ttl)

            if model_selection_policy is None:
                # go out in case the policy based requirement is None, which means model was asked by name
                raise

            fallback_model = await self.get_best_model(
                model_selection_policy, user_message=messages[-1] if model_selection_policy == "smart" else None
            )
            if fallback_model is None or fallback_model == model_name:
                #in case the model which is out, was the only best case
                raise

            return await self.invoke_model(fallback_model, messages, max_tokens, model_selection_policy=None)

        analytics_object = AnalyticsJobData(
            model_name=model_name,
            input_tokens=model_response.input_tokens,
            output_tokens=model_response.output_tokens,
            latency_ms=latency_ms,
            timestamp=datetime.now().isoformat()
        )

        await self.router_adapter.add_job_to_queue(collection_name=RedisStreamName.ANALYTICS, data=analytics_object) #type: ignore
        return model_response.content

    async def get_best_model(self, requirement: str, user_message: Message | None = None) -> str:
        if requirement in {"fast", "cheap"}:
            return await self.router_adapter.get_best_model(requirement)
        elif requirement in {"smart"}:
            return await self.router_adapter.identify_model_intelligently(user_message.content) #type: ignore
        else:
            return self.config.get_config(ConfigurationSection.GATEWAY, ConfigurationOption.DEFAULT_MODEL)