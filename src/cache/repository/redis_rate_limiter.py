from __future__ import annotations

import math
from pathlib import Path
from typing import override, TYPE_CHECKING

from src.app.ports import RateLimiterInterface
from src.utils.types import CacheType, ConfigurationSection, ConfigurationOption, RateLimitDecision

from ..connection import CacheConnection

if TYPE_CHECKING:
    from src.utils.config import Config

_BUCKET_KEY_PREFIX = "ratelimit:"
# the atomic token bucket; see the comments in the file
_TAKE_TOKEN_SCRIPT = Path(__file__).parent.parent / "scripts" / "take_token.lua"


class RedisRateLimiter(RateLimiterInterface):
    def __init__(self, config: Config):
        self.cache_conn = CacheConnection.get_connection(CacheType.EXACT)
        self.max_tokens = int(config.get_config(ConfigurationSection.RATE_LIMITER, ConfigurationOption.MAX_TOKENS))
        self.refill_rate = int(config.get_config(ConfigurationSection.RATE_LIMITER, ConfigurationOption.REFILL_RATE))
        self.time_interval = float(config.get_config(ConfigurationSection.RATE_LIMITER, ConfigurationOption.TIME_INTERVAL))
        # a bucket left alone this long is full again, so Redis can drop it: an absent bucket starts full
        self._bucket_ttl_seconds = max(1, math.ceil(math.ceil(self.max_tokens / self.refill_rate) * self.time_interval))
        self._take_token = self.cache_conn.register_script(_TAKE_TOKEN_SCRIPT.read_text())

    @override
    async def acquire(self, user_id: str) -> RateLimitDecision:
        allowed, remaining, reset_at = await self._take_token(
            keys=[f"{_BUCKET_KEY_PREFIX}{user_id}"],
            args=[self.max_tokens, self.refill_rate, self.time_interval, self._bucket_ttl_seconds],
        )
        return RateLimitDecision(allowed=bool(allowed), limit=self.max_tokens, remaining=int(remaining),
                                 reset_at=float(reset_at))
