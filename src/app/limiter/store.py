import threading
from collections import defaultdict

from src.utils.config import Config
from src.utils.types import ConfigurationSection, ConfigurationOption
from .bucket import TokenBucket

class RateLimiterStore:
    def __init__(self):
        self.config = Config()

        self.max_tokens = int(self.config.get_config(ConfigurationSection.RATE_LIMITER, ConfigurationOption.MAX_TOKENS))
        self.refill_rate = int(self.config.get_config(ConfigurationSection.RATE_LIMITER, ConfigurationOption.REFILL_RATE))
        self.time_interval = float(self.config.get_config(ConfigurationSection.RATE_LIMITER, ConfigurationOption.TIME_INTERVAL))

        self.buckets: dict[str, TokenBucket] = defaultdict(lambda: TokenBucket(
            max_tokens=self.max_tokens,
            refill_rate=self.refill_rate,
            time_interval=self.time_interval
        ))

        self.lock = threading.Lock()

    def get_user_bucket(self, user_id: str):
        with self.lock:
            return self.buckets[user_id]
