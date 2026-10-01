"""Token bucket rate limiting middleware for FastAPI."""

import time
from typing import Dict, Tuple
from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, requests_per_minute: int = 60) -> None:
        self.capacity = requests_per_minute
        self.refill_rate = requests_per_minute / 60.0  # tokens per second
        self.tokens: Dict[str, float] = {}
        self.last_update: Dict[str, float] = {}

    def check_rate_limit(self, client_id: str) -> None:
        now = time.time()
        if client_id not in self.tokens:
            self.tokens[client_id] = self.capacity
            self.last_update[client_id] = now

        elapsed = now - self.last_update[client_id]
        self.tokens[client_id] = min(self.capacity, self.tokens[client_id] + elapsed * self.refill_rate)
        self.last_update[client_id] = now

        if self.tokens[client_id] < 1.0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please wait before making more requests.",
            )

        self.tokens[client_id] -= 1.0


default_rate_limiter = RateLimiter(requests_per_minute=60)
