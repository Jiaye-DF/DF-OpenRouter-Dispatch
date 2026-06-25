"""判別模型設定 API 測試(對齊 docs/Tasks/v2.0/task-002-judge-settings-api.md Acceptance)。

沿用本專案 mock 風格(見 tests/services/test_api_key_request_router.py):
- FastAPI app + httpx.AsyncClient(ASGITransport)。
- dependency_overrides 覆寫 require_admin(假 admin Actor)與 get_db(假 AsyncSession)。
- monkeypatch ai_eval 模組內 AiEvalJudgeSettingRepository 為可控 in-memory 假物件。
不連真 DB。
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.v1.ai_eval as ai_eval
from app.core.database import get_db
from app.core.deps import require_admin
from app.main import create_app
from app.schemas.actor import Actor


class _FakeModel:
    def __init__(self, model_uid: UUID, model_key: str, name: str) -> None:
        self.model_uid = model_uid
        self.model_key = model_key
        self.name = name


class _FakeSetting:
    def __init__(self, model_uid: UUID, slot: int) -> None:
        self.model_uid = model_uid
        self.ai_judge_slot = slot
        self.is_active = True
        self.is_deleted = False


class _Store:
    """跨 request 共享的後端狀態(取代 DB)。"""

    def __init__(self, active_models: list[_FakeModel]) -> None:
        self.active_models = {m.model_uid: m for m in active_models}
        self.settings: list[_FakeSetting] = []


class _FakeRepo:
    """ai_eval.AiEvalJudgeSettingRepository 的替身;狀態存於 class 變數 store。"""

    store: _Store

    def __init__(self, db) -> None:
        self.db = db

    async def list_active(self):
        return sorted(
            [s for s in self.store.settings if s.is_active and not s.is_deleted],
            key=lambda s: s.ai_judge_slot,
        )

    async def soft_delete_active(self):
        for s in self.store.settings:
            if s.is_active and not s.is_deleted:
                s.is_active = False
                s.is_deleted = True

    def add(self, row):
        # endpoint 傳入真 AiEvalJudgeSetting；轉成 _FakeSetting 落地
        self.store.settings.append(
            _FakeSetting(row.model_uid, row.ai_judge_slot)
        )

    async def list_active_models_by_uids(self, model_uids):
        return [
            self.store.active_models[u]
            for u in model_uids
            if u in self.store.active_models
        ]


class _FakeDb:
    async def flush(self):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None

    def add(self, row):  # write_audit -> db.add
        return None


@pytest.fixture
def admin_actor() -> Actor:
    return Actor(
        user_uid=uuid4(),
        account="admin",
        username="系統管理員",
        role="admin",
    )


def _make_client(monkeypatch, store: _Store, admin_actor: Actor | None):
    """建 app + client;admin_actor=None 表示不覆寫 require_admin(走真實鑑權)。"""
    _FakeRepo.store = store
    monkeypatch.setattr(ai_eval, "AiEvalJudgeSettingRepository", _FakeRepo)

    app = create_app()

    async def _fake_get_db():
        yield _FakeDb()

    app.dependency_overrides[get_db] = _fake_get_db
    if admin_actor is not None:
        app.dependency_overrides[require_admin] = lambda: admin_actor

    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def _three_models() -> list[_FakeModel]:
    return [
        _FakeModel(uuid4(), "openai/gpt-4o", "GPT-4o"),
        _FakeModel(uuid4(), "anthropic/claude-3.5", "Claude 3.5"),
        _FakeModel(uuid4(), "google/gemini-pro", "Gemini Pro"),
    ]


async def test_get_returns_envelope_with_current_settings(monkeypatch, admin_actor):
    models = _three_models()
    store = _Store(models)
    store.settings = [_FakeSetting(m.model_uid, i + 1) for i, m in enumerate(models)]
    async with _make_client(monkeypatch, store, admin_actor) as client:
        resp = await client.get("/api/v1/ai-eval/judge-settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["code"] == 200
    assert body["detail"] == "success"
    assert len(body["data"]) == 3
    slots = [d["ai_judge_slot"] for d in body["data"]]
    assert slots == [1, 2, 3]
    first = body["data"][0]
    assert set(first.keys()) == {"ai_judge_slot", "model_uid", "model_key", "name"}
    assert first["model_uid"] == str(models[0].model_uid)


async def test_put_three_active_then_get_returns_same(monkeypatch, admin_actor):
    models = _three_models()
    store = _Store(models)
    uids = [str(m.model_uid) for m in models]
    async with _make_client(monkeypatch, store, admin_actor) as client:
        put = await client.put(
            "/api/v1/ai-eval/judge-settings", json={"model_uids": uids}
        )
        assert put.status_code == 200, put.text
        put_body = put.json()
        assert put_body["success"] is True
        assert [d["model_uid"] for d in put_body["data"]] == uids
        assert [d["ai_judge_slot"] for d in put_body["data"]] == [1, 2, 3]

        get = await client.get("/api/v1/ai-eval/judge-settings")
    get_body = get.json()
    assert [d["model_uid"] for d in get_body["data"]] == uids


async def test_put_overwrite_no_slot_conflict(monkeypatch, admin_actor):
    """已有設定下再 PUT 一組(含部分重疊)應成功(軟刪舊→寫新)。"""
    models = _three_models()
    extra = _FakeModel(uuid4(), "x/extra", "Extra")
    store = _Store([*models, extra])
    store.settings = [_FakeSetting(m.model_uid, i + 1) for i, m in enumerate(models)]
    new_uids = [
        str(models[0].model_uid),
        str(models[1].model_uid),
        str(extra.model_uid),
    ]
    async with _make_client(monkeypatch, store, admin_actor) as client:
        put = await client.put(
            "/api/v1/ai-eval/judge-settings", json={"model_uids": new_uids}
        )
    assert put.status_code == 200, put.text
    assert [d["model_uid"] for d in put.json()["data"]] == new_uids


async def test_put_not_three_returns_422(monkeypatch, admin_actor):
    models = _three_models()
    store = _Store(models)
    uids = [str(models[0].model_uid), str(models[1].model_uid)]
    async with _make_client(monkeypatch, store, admin_actor) as client:
        resp = await client.put(
            "/api/v1/ai-eval/judge-settings", json={"model_uids": uids}
        )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "judge_models_must_be_three"


async def test_put_duplicated_returns_422(monkeypatch, admin_actor):
    models = _three_models()
    store = _Store(models)
    uids = [str(models[0].model_uid), str(models[0].model_uid), str(models[1].model_uid)]
    async with _make_client(monkeypatch, store, admin_actor) as client:
        resp = await client.put(
            "/api/v1/ai-eval/judge-settings", json={"model_uids": uids}
        )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "judge_models_duplicated"


async def test_put_nonexistent_returns_422(monkeypatch, admin_actor):
    models = _three_models()
    store = _Store(models)
    uids = [str(models[0].model_uid), str(models[1].model_uid), str(uuid4())]
    async with _make_client(monkeypatch, store, admin_actor) as client:
        resp = await client.put(
            "/api/v1/ai-eval/judge-settings", json={"model_uids": uids}
        )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "judge_model_not_active"


async def test_put_inactive_or_soft_deleted_returns_422(monkeypatch, admin_actor):
    """已停用 / 軟刪除模型不在 active 清單 → 422。"""
    models = _three_models()
    # store 只把前兩個列為 active；第三個 uid 視為已停用 / 軟刪除(不在 active_models)
    inactive = _FakeModel(uuid4(), "x/dead", "Dead")
    store = _Store([models[0], models[1]])
    uids = [str(models[0].model_uid), str(models[1].model_uid), str(inactive.model_uid)]
    async with _make_client(monkeypatch, store, admin_actor) as client:
        resp = await client.put(
            "/api/v1/ai-eval/judge-settings", json={"model_uids": uids}
        )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "judge_model_not_active"


async def test_no_admin_cookie_returns_401(monkeypatch):
    """不覆寫 require_admin、不帶 cookie → 401。"""
    store = _Store(_three_models())
    async with _make_client(monkeypatch, store, admin_actor=None) as client:
        resp = await client.get("/api/v1/ai-eval/judge-settings")
    assert resp.status_code == 401


async def test_non_admin_returns_403(monkeypatch):
    """登入但非 admin → 403(覆寫 require_user 回 user 角色,require_admin 走真實判斷)。"""
    from app.core.deps import require_user

    store = _Store(_three_models())
    _FakeRepo.store = store
    monkeypatch.setattr(ai_eval, "AiEvalJudgeSettingRepository", _FakeRepo)
    app = create_app()

    async def _fake_get_db():
        yield _FakeDb()

    user_actor = Actor(
        user_uid=uuid4(), account="u", username="一般使用者", role="user"
    )
    app.dependency_overrides[get_db] = _fake_get_db
    app.dependency_overrides[require_user] = lambda: user_actor

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/ai-eval/judge-settings")
    assert resp.status_code == 403
