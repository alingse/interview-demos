"""Token bucket rate limiter."""

import asyncio
import time
from typing import Optional


class RateLimiter:
    """Token bucket rate limiter for API rate limiting.

    Args:
        rate: Tokens per second (e.g., 3.0 for 3 requests/second)
        burst: Maximum burst size (bucket capacity)
    """

    def __init__(self, rate: float = 3.0, burst: int = 5):
        self.rate = rate
        self.burst = burst
        self.tokens: float = float(burst)
        self.last_update: float = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update

            # Replenish tokens based on elapsed time
            self.tokens = min(
                self.burst, self.tokens + elapsed * self.rate
            )
            self.last_update = now

            # Wait if we don't have enough tokens
            while self.tokens < tokens:
                wait_time = (tokens - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                now = time.monotonic()
                elapsed = now - self.last_update
                self.tokens = min(
                    self.burst, self.tokens + elapsed * self.rate
                )
                self.last_update = now

            # Deduct tokens
            self.tokens -= tokens

    def can_acquire(self, tokens: int = 1) -> bool:
        """Check if tokens are available without waiting.

        Args:
            tokens: Number of tokens to check

        Returns:
            True if tokens are available
        """
        now = time.monotonic()
        elapsed = now - self.last_update
        current_tokens = min(self.burst, self.tokens + elapsed * self.rate)
        return current_tokens >= tokens

    async def __aenter__(self):
        """Async context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass


class ConcurrencyLimiter:
    """Limit concurrent operations using semaphore.

    Args:
        max_concurrent: Maximum concurrent operations
    """

    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent

    async def __aenter__(self):
        """Acquire semaphore."""
        await self.semaphore.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release semaphore."""
        self.semaphore.release()
