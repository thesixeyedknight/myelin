from __future__ import annotations
import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    capacity: int
    refill_rate_per_sec: float
    tokens: float = 0.0
    last: float = time.time()

    def take(self, n: int = 1):
        now = time.time()
        elapsed = now - self.last
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate_per_sec)
        self.last = now
        if self.tokens < n:
            needed = n - self.tokens
            time.sleep(max(0, needed / self.refill_rate_per_sec))
            self.tokens = 0
            self.last = time.time()
        else:
            self.tokens -= n


# Free-tier friendly defaults. Adjust as needed for RPM.
LLM_RPM = TokenBucket(capacity=10, refill_rate_per_sec=10 / 60.0)
