from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.utils.types import Message

EXACT_CACHE_KEY_PREFIX = "cache:exact:"


@dataclass(frozen=True)
class CacheKeys:
    exact_key: str      # Redis key for the whole request
    context_hash: str   # everything except the prompt; semantic hits must match it exactly
    prompt: str         # the last user message, the only part that is embedded


class CacheKeyBuilder:

    def build_cache_keys(self, user_id: str | None, model: str, temperature: float | None, messages: list[Message]) -> CacheKeys:
        prompt_index = max(index for index, message in enumerate(messages) if message.role == "user")
        scope = {"user_id": user_id, "model": model, "temperature": temperature}
        serialized = [message.model_dump() for message in messages]

        context = serialized[:prompt_index] + serialized[prompt_index + 1:]

        return CacheKeys(
            exact_key=EXACT_CACHE_KEY_PREFIX + self._digest({**scope, "messages": serialized}),
            context_hash=self._digest({**scope, "context": context, "prompt_index": prompt_index}),
            prompt=messages[prompt_index].content,
        )

    def _digest(self, data: dict) -> str:
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()

