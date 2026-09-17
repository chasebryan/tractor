import asyncio
import time


class RateLimiter:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._next: dict[str, float] = {}

    async def wait(self, host: str, interval: float) -> None:
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            await asyncio.sleep(max(0, self._next.get(host, 0) - time.monotonic()))
            self._next[host] = time.monotonic() + interval
