import threading
from collections import defaultdict

from src.utils.config import Config
from .bucket import TokenBucket

class RateLimiterStore:
    def __init__(self):
        self.config = Config()

        self.max_tokens = int(self.config.get_config("RATE_LIMITER", "MAX_TOKENS"))
        self.refill_rate = int(self.config.get_config("RATE_LIMITER", "REFILL_RATE"))
        self.time_interval = float(self.config.get_config("RATE_LIMITER", "TIME_INTERVAL"))

        self.buckets: dict[str, TokenBucket] = defaultdict(lambda: TokenBucket(
            max_tokens=self.max_tokens,
            refill_rate=self.refill_rate,
            time_interval=self.time_interval
        ))

        self.lock = threading.Lock()

    def get_user_bucket(self, user_id: str):
        with self.lock:
            return self.buckets[user_id]
