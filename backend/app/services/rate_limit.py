"""速率限制(v1.2)— Key 級 RPM + 最小間隔。

對齊 docs/Tasks/v1.2/propose-v1.2.0.md § 6。

設計:
- 滾動 60 秒視窗 RPM + 最小間隔守門,兩者疊加取較大等待時間。
- 預訂(deque.append)在 asyncio.Lock 內完成,保證 FIFO。
- 鎖外才 asyncio.sleep,避免阻塞其他 Key 的 limiter。
- 限制:單 uvicorn worker 進程內生效;multi-worker 需升級 Redis 版(v1.3)。
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Hashable


class RateLimitExceeded(Exception):
    """需等待 `retry_after_seconds` 才能取得 slot;超過呼叫端設定的 wait_timeout。"""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(f"need wait {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds


class KeyRateLimiter:
    """單 Key 速率限制器。"""

    def __init__(self) -> None:
        # 已預訂(包含實際發出時間 ≥ now)的 slot 時間戳
        self._reserved: deque[float] = deque()
        self._last_request_ts: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(
        self,
        *,
        rpm_limit: int,
        min_interval_ms: int,
        wait_timeout: float,
    ) -> None:
        """預訂一個發出 slot;若需等待 > wait_timeout,拋 `RateLimitExceeded`。

        `rpm_limit=0` 或 `min_interval_ms=0` 視為對應維度不限。
        """
        min_interval = min_interval_ms / 1000

        async with self._lock:
            now = time.monotonic()

            # 1) 清除 60 秒前的舊紀錄
            while self._reserved and self._reserved[0] <= now - 60:
                self._reserved.popleft()

            # 2) 計算需等待秒數
            waits: list[float] = []
            if min_interval > 0 and self._last_request_ts + min_interval > now:
                waits.append(self._last_request_ts + min_interval - now)
            if rpm_limit > 0 and len(self._reserved) >= rpm_limit:
                waits.append(self._reserved[0] + 60 - now)
            wait = max(waits) if waits else 0.0

            if wait > wait_timeout:
                # 不預訂;讓上層決定 fallback(failover / 429)
                raise RateLimitExceeded(retry_after_seconds=int(wait) + 1)

            # 3) 預訂 slot(以「實際發出時間」為準),保證 FIFO
            start_ts = now + wait
            self._reserved.append(start_ts)
            self._last_request_ts = start_ts

        if wait > 0:
            await asyncio.sleep(wait)


_registry: dict[Hashable, KeyRateLimiter] = {}
_registry_lock = asyncio.Lock()


async def get_limiter(key: Hashable) -> KeyRateLimiter:
    """取得指定 key 的 limiter;首次呼叫 lazy 建立。"""
    limiter = _registry.get(key)
    if limiter is not None:
        return limiter
    async with _registry_lock:
        limiter = _registry.get(key)
        if limiter is None:
            limiter = KeyRateLimiter()
            _registry[key] = limiter
        return limiter


def _reset_registry_for_tests() -> None:
    """測試用:清空 registry,避免測試間互相污染。生產程式碼勿呼叫。"""
    _registry.clear()
