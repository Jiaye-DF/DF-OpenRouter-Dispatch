"""rate_limit.py 單元測試 — 對齊 tasks-v1.2.0.md § 測試。"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.services.rate_limit import (
    KeyRateLimiter,
    RateLimitExceeded,
    _reset_registry_for_tests,
    get_limiter,
)


@pytest.fixture(autouse=True)
def _reset_registry():
    _reset_registry_for_tests()
    yield
    _reset_registry_for_tests()


@pytest.mark.asyncio
async def test_acquire_unlimited_passes_immediately():
    """rpm_limit=0 + min_interval_ms=0 應立即通過,不等待。"""
    limiter = KeyRateLimiter()
    start = time.monotonic()
    for _ in range(5):
        await limiter.acquire(rpm_limit=0, min_interval_ms=0, wait_timeout=0)
    elapsed = time.monotonic() - start
    assert elapsed < 0.05, f"應立即通過,實際 {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_min_interval_enforces_gap():
    """min_interval_ms=200 → 連兩次呼叫間隔需 >= 200ms。"""
    limiter = KeyRateLimiter()
    t0 = time.monotonic()
    await limiter.acquire(rpm_limit=0, min_interval_ms=200, wait_timeout=5)
    t1 = time.monotonic()
    await limiter.acquire(rpm_limit=0, min_interval_ms=200, wait_timeout=5)
    t2 = time.monotonic()
    assert t1 - t0 < 0.05, "第一次應立即"
    assert t2 - t1 >= 0.18, f"第二次應等 ~200ms,實際 {t2 - t1:.3f}s"


@pytest.mark.asyncio
async def test_rpm_limit_blocks_n_plus_one():
    """rpm_limit=2:連 3 次,第 3 次 wait_timeout=0 → RateLimitExceeded。"""
    limiter = KeyRateLimiter()
    await limiter.acquire(rpm_limit=2, min_interval_ms=0, wait_timeout=0)
    await limiter.acquire(rpm_limit=2, min_interval_ms=0, wait_timeout=0)
    with pytest.raises(RateLimitExceeded) as exc_info:
        await limiter.acquire(rpm_limit=2, min_interval_ms=0, wait_timeout=0)
    assert exc_info.value.retry_after_seconds >= 1


@pytest.mark.asyncio
async def test_wait_timeout_exceeded_raises():
    """需等待 > wait_timeout → RateLimitExceeded,且不佔位。"""
    limiter = KeyRateLimiter()
    await limiter.acquire(rpm_limit=1, min_interval_ms=0, wait_timeout=0)
    with pytest.raises(RateLimitExceeded):
        await limiter.acquire(rpm_limit=1, min_interval_ms=0, wait_timeout=0.5)


@pytest.mark.asyncio
async def test_rpm_window_slides_after_60s(monkeypatch):
    """假時鐘:60 秒外的舊紀錄被清除,新請求可立即通過。"""
    limiter = KeyRateLimiter()
    real_monotonic = time.monotonic
    fake_now = [real_monotonic()]

    def fake_monotonic() -> float:
        return fake_now[0]

    monkeypatch.setattr("app.services.rate_limit.time.monotonic", fake_monotonic)

    await limiter.acquire(rpm_limit=1, min_interval_ms=0, wait_timeout=0)
    # 推進 61 秒
    fake_now[0] += 61
    await limiter.acquire(rpm_limit=1, min_interval_ms=0, wait_timeout=0)


@pytest.mark.asyncio
async def test_get_limiter_reuses_same_instance():
    """同 key 取回同一個 limiter 實例。"""
    a = await get_limiter("KEY_A")
    b = await get_limiter("KEY_A")
    c = await get_limiter("KEY_B")
    assert a is b
    assert a is not c
