"""api_key_request_router.route() 單元測試 — 對齊 tasks-v1.9.1.md § 規則路由 / 測試重點。

route() 內部以 db 建構三個 repository;此處 monkeypatch 那三個 repository 類別為
可控假物件,專測決策樹本身(不需真實 DB)。
"""

from __future__ import annotations

from uuid import uuid4

import pytest

import app.services.api_key_request_router as router
from app.models.api_key_request import ApiKeyRequest
from app.models.department import Department


def _req(**over) -> ApiKeyRequest:
    base = dict(
        department_name="資訊部",
        department_code="IT",
        project_name="客服機器人",
        project_url="https://github.com/df/bot",
        owner_name="王小明",
        owner_email="ming@df-recycle.com.tw",
    )
    base.update(over)
    return ApiKeyRequest(**base)


def _dept(name: str = "資訊部", code: str = "IT") -> Department:
    return Department(department_uid=uuid4(), code=code, name=name)


def _patch(monkeypatch, *, dept, proj, users):
    """把 router 模組內三個 repository 類別換成回傳預設值的假物件。"""

    class FakeDept:
        def __init__(self, db):
            pass

        async def get_by_code(self, code):
            return dept

    class FakeProj:
        def __init__(self, db):
            pass

        async def get_active_by_department_and_name(self, department_uid, name):
            return proj

    class FakeUser:
        def __init__(self, db):
            pass

        async def list_by_email(self, email):
            return users

    monkeypatch.setattr(router, "DepartmentRepository", FakeDept)
    monkeypatch.setattr(router, "ProjectRepository", FakeProj)
    monkeypatch.setattr(router, "UserRepository", FakeUser)


@pytest.mark.asyncio
async def test_new_department_goes_manual(monkeypatch):
    """部門不存在 → 人工(新部門需後台建 Key)。"""
    _patch(monkeypatch, dept=None, proj=None, users=[])
    res = await router.route(None, _req())
    assert res.decision == "manual"
    assert "新部門" in res.reason
    assert res.matched_department is None


@pytest.mark.asyncio
async def test_department_name_mismatch_goes_manual(monkeypatch):
    """代號命中但名稱對不上 → 硬規則人工(先於 AI)。"""
    _patch(monkeypatch, dept=_dept(name="財務部"), proj=None, users=[])
    res = await router.route(None, _req(department_name="資訊部"))
    assert res.decision == "manual"
    assert "不符" in res.reason


@pytest.mark.asyncio
async def test_old_dept_new_project_single_user_goes_ai(monkeypatch):
    """舊部門 + 新專案 + email 命中唯一 → AI;沿用部門與該使用者。"""
    dept = _dept()
    user = object()
    _patch(monkeypatch, dept=dept, proj=None, users=[user])
    res = await router.route(None, _req())
    assert res.decision == "ai"
    assert res.reason is None
    assert res.matched_department is dept
    assert res.matched_user is user


@pytest.mark.asyncio
async def test_old_dept_new_project_new_user_goes_ai(monkeypatch):
    """舊部門 + 新專案 + 新使用者 → AI;matched_user 為 None。"""
    dept = _dept()
    _patch(monkeypatch, dept=dept, proj=None, users=[])
    res = await router.route(None, _req())
    assert res.decision == "ai"
    assert res.matched_user is None


@pytest.mark.asyncio
async def test_new_project_multi_user_still_ai_no_match(monkeypatch):
    """新專案分支:email 多筆不擋(仍 AI),只是不沿用單一使用者。"""
    dept = _dept()
    _patch(monkeypatch, dept=dept, proj=None, users=[object(), object()])
    res = await router.route(None, _req())
    assert res.decision == "ai"
    assert res.matched_user is None


@pytest.mark.asyncio
async def test_old_project_multi_user_goes_manual(monkeypatch):
    """舊專案 + email 命中多筆 → 硬規則歧義人工。"""
    _patch(monkeypatch, dept=_dept(), proj=object(), users=[object(), object()])
    res = await router.route(None, _req())
    assert res.decision == "manual"
    assert "多筆" in res.reason


@pytest.mark.asyncio
async def test_old_project_new_user_goes_manual(monkeypatch):
    """舊專案 + 新使用者 → 人工(既有專案加新成員)。"""
    _patch(monkeypatch, dept=_dept(), proj=object(), users=[])
    res = await router.route(None, _req())
    assert res.decision == "manual"
    assert "新使用者" in res.reason


@pytest.mark.asyncio
async def test_all_existing_goes_system_cancel(monkeypatch):
    """舊部門 + 舊專案 + 舊使用者(唯一) → 系統取消(重複)。"""
    _patch(monkeypatch, dept=_dept(), proj=object(), users=[object()])
    res = await router.route(None, _req())
    assert res.decision == "system_cancel"
    assert res.reason == "過去已存在相同 Key 資料"
