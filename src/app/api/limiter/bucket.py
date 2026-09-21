import time
import threading

class TokenBucket:
    def __init__(self, max_tokens: int, refill_rate: int, time_interval: float) -> None:
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.time_interval = time_interval

        self.current_tokens = max_tokens
        self.last_refill_time = time.time()
        self.lock = threading.Lock()

    def refill(self):
        now = time.time()
        elapsed = now - self.last_refill_time

        if elapsed >= self.time_interval:
            num_refills = int(elapsed // self.time_interval)
            self.current_tokens = min(self.max_tokens, self.current_tokens + num_refills*self.refill_rate)
            self.last_refill_time += num_refills*self.time_interval

    def request_allowed(self, tokens: int = 1) -> bool:
        with self.lock:
            self.refill()

            if self.current_tokens >= tokens:
                self.current_tokens -= tokens
                return True
        return False

    def get_reset_time(self) -> float:
        with self.lock:
            return self.last_refill_time + self.time_interval

    def get_remaining(self):
        with self.lock:
            self.refill()
            return self.current_tokens

