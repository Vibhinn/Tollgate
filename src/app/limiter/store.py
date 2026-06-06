import threading
from collections import defaultdict

from src.utils.config import configurations
from .bucket import TokenBucket

class RateLimiterStore:
    def __init__(self):

        self.max_tokens = int(configurations.get_config("RATE_LIMITER", "MAX_TOKENS"))
        self.refill_rate = int(configurations.get_config("RATE_LIMITER", "REFILL_RATE"))
        self.time_interval = float(configurations.get_config("RATE_LIMITER", "TIME_INTERVAL"))

        self.buckets: dict[str, TokenBucket] = defaultdict(lambda: TokenBucket(
            max_tokens=self.max_tokens,
            refill_rate=self.refill_rate,
            time_interval=self.time_interval
        ))

        self.lock = threading.Lock()

    def get_user_bucket(self, user_id: str):
        with self.lock:
            return self.buckets[user_id]
