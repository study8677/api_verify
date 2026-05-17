from __future__ import annotations

import logging
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class RateLimiter:
    """Per-IP hourly verification budget.

    Backed by redis when available; falls back to an in-process dict when not
    (useful for local dev / when redis is down — fails open with logging).
    """

    def __init__(self, redis_url: str | None, max_per_hour: int = 5):
        self.max = max_per_hour
        self._redis = None
        self._mem: dict[str, tuple[int, float]] = {}
        if redis_url:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(redis_url, decode_responses=True)
                log.info("rate limiter using redis at %s", _scrub(redis_url))
            except Exception as exc:  # ImportError or connection-time error
                log.warning("redis unavailable (%s); using in-memory rate limit fallback", exc)

    async def check(self, ip: str) -> RateLimitResult:
        bucket = int(time.time() // 3600)
        key = f"apiverify:rl:{ip}:{bucket}"
        if self._redis is not None:
            try:
                count = await self._redis.incr(key)
                if count == 1:
                    await self._redis.expire(key, 3600)
                allowed = count <= self.max
                remaining = max(0, self.max - count)
                retry = 3600 - int(time.time()) % 3600 if not allowed else 0
                return RateLimitResult(allowed=allowed, remaining=remaining, retry_after_seconds=retry)
            except Exception as exc:
                log.warning("redis rate-limit failed open: %s", exc)
        # in-memory fallback
        now = time.time()
        self._prune_mem(now)
        count, expires = self._mem.get(key, (0, now + 3600))
        if expires < now:
            count, expires = 0, now + 3600
        count += 1
        self._mem[key] = (count, expires)
        allowed = count <= self.max
        return RateLimitResult(
            allowed=allowed,
            remaining=max(0, self.max - count),
            retry_after_seconds=int(expires - now) if not allowed else 0,
        )

    def _prune_mem(self, now: float) -> None:
        # Drop expired buckets, and cap total entries to keep memory bounded
        # under an IP-rotation attack when redis is unavailable.
        if len(self._mem) > 20_000:
            expired = [k for k, (_, exp) in self._mem.items() if exp < now]
            for k in expired:
                self._mem.pop(k, None)
            if len(self._mem) > 20_000:
                # still too large — drop the oldest by expiry
                victims = sorted(self._mem.items(), key=lambda kv: kv[1][1])[: len(self._mem) - 10_000]
                for k, _ in victims:
                    self._mem.pop(k, None)

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass


def _scrub(url: str) -> str:
    # don't leak credentials in logs
    if "@" in url:
        scheme, _, rest = url.partition("://")
        _, _, hostpart = rest.partition("@")
        return f"{scheme}://***@{hostpart}"
    return url
