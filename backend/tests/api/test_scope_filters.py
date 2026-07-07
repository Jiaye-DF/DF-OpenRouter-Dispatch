"""app.api.v1._scope_filters.resolve_filters 單元測試。

resolve_filters 為 stats 與 usage-logs 共用的部門鎖工具;此檔直接對其行為斷言,
確保「非-admin 無部門 → 403」防線(scan 報告 AD-001 / fixed.md §10)不回退。
純函式、無 I/O,故不需 asyncio / DB。
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.api.v1._scope_filters import resolve_filters
from app.core.exceptions import AppError
from app.schemas.actor import Actor


def _admin() -> Actor:
    return Actor(user_uid=uuid4(), account="a", username="管理員", role="admin")


def _user(dept=None) -> Actor:
    return Actor(
        user_uid=uuid4(),
        account="u",
        username="一般使用者",
        role="user",
        department_uid=dept,
    )


def test_admin_passthrough_no_lock():
    dept, proj, user = uuid4(), uuid4(), uuid4()
    assert resolve_filters(_admin(), dept, proj, user) == (dept, proj, user)


def test_admin_all_none_passthrough():
    assert resolve_filters(_admin(), None, None, None) == (None, None, None)


def test_non_admin_locks_own_department():
    dept = uuid4()
    proj = uuid4()
    assert resolve_filters(_user(dept), None, proj, None) == (dept, proj, None)


def test_non_admin_cross_department_raises_403():
    with pytest.raises(AppError) as ei:
        resolve_filters(_user(uuid4()), uuid4(), None, None)
    assert ei.value.code == 403


def test_non_admin_without_department_raises_403():
    # AD-001:非-admin 且無部門 → 一律 403,不得退化為 department_uid=None(無過濾)。
    with pytest.raises(AppError) as ei:
        resolve_filters(_user(None), None, None, None)
    assert ei.value.code == 403
