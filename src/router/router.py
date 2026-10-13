from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING

from src.app.exceptions import (
    ModelSemanticNotFound, APIKeyInvalidOrExpired, CreditExhaustion,
    PermissionDeniedForModel, RateLimitedFromModelProvider, ModelProviderServerError, APIError,
)
from src.utils.types import (AnalyticsJobData, RedisStreamName, ConfigurationSection, ConfigurationOption, Message,
                             GenerationParams, LLMInvocationResult, last_user_message)
from src.utils.config import ROUTING_TABLE
from src.llm import LLMRepositoryFactory

from src.app.adapters import RouterAdapter

if TYPE_CHECKING:
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
                                        APIError: 30,
                                    }

    async def invoke_model(self, model_name: str, messages: list[Message], params: GenerationParams,
                           model_selection_policy: str | None = None) -> LLMInvocationResult:
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
            model_response = await repository.invoke(messages, real_model_name, params)
            latency_ms: float = (time.monotonic() - start)*1000
        except tuple(self._TTL_BY_EXCEPTION_MAP) as e:
            ttl: int = self._TTL_BY_EXCEPTION_MAP[type(e)]
            await self.router_adapter.mark_model_unavailable(model_name, ttl)
            await self.router_adapter.add_job_to_queue(collection_name=RedisStreamName.ANALYTICS, data=AnalyticsJobData(
                model_name=model_name, input_tokens=0, output_tokens=0, latency_ms=0.0,
                timestamp=datetime.now().isoformat(), succeeded=False,
            ))

            if model_selection_policy is None:
                raise

            fallback_model = await self.get_best_model(
                model_selection_policy, user_message=last_user_message(messages) if model_selection_policy == "smart" else None
            )
            if fallback_model is None or fallback_model == model_name:
                raise

            return await self.invoke_model(fallback_model, messages, params, model_selection_policy=None)

        analytics_object = AnalyticsJobData(
            model_name=model_name,
            input_tokens=model_response.input_tokens,
            output_tokens=model_response.output_tokens,
            latency_ms=latency_ms,
            timestamp=datetime.now().isoformat(),
            succeeded=True,
        )

        await self.router_adapter.add_job_to_queue(collection_name=RedisStreamName.ANALYTICS, data=analytics_object)
        return replace(model_response, model=model_name)

    async def get_best_model(self, requirement: str, user_message: Message | None = None) -> str:
        if requirement in {"fast", "cheap"}:
            return await self.router_adapter.get_best_model(requirement)
        elif requirement in {"smart"}:
            return await self.router_adapter.identify_model_intelligently(user_message.content) #type: ignore
        else:
            return self.config.get_config(ConfigurationSection.GATEWAY, ConfigurationOption.DEFAULT_MODEL)

    def has_model(self, model_name: str) -> bool:
        entry = self.routing_table.get(model_name)
        return entry is not None and self.llm_repo_factory.get_repo(entry.get("provider")) is not None

    def available_models(self) -> dict[str, str]:
        return {
            model_name: entry.get("provider") for model_name, entry in self.routing_table.items()
            if self.llm_repo_factory.get_repo(entry.get("provider")) is not None
        }

    async def seconds_until_a_model_returns(self) -> int | None:
        """Seconds until the first benched model is back in rotation; None when none is benched."""
        return await self.router_adapter.seconds_until_available(list(self.available_models()))

    async def warm_up_latency_rankings(self) -> None:
        probe_message = [Message(role="user", content="Hi")]
        candidates = list(self.available_models())

        await asyncio.gather(*(self._probe(model_name, probe_message) for model_name in candidates))


    async def _probe(self, model_name: str, probe_message: list[Message]) -> None:
        try:
            await self.invoke_model(model_name, probe_message, GenerationParams(max_tokens=1))
        except Exception:
            pass
