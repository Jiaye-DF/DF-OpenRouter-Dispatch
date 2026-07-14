"""
End-to-end smoke test for DF-OpenRouter-Dispatch.

流程（base 供裝，所有 scenario 共用）：
1. 登入初始 admin 取得 Cookie
2. 建立 TEST 部門
3. 建立 test.user 使用者於 TEST 部門（含 email/employee_id；以 email 冪等重用）
4. 建立 TEST 部門的 OpenRouter Key（同名 E2E-Smoke 已存在則重用）
5. 建立 TEST 部門的專案（取得 X-Project-Code；同名重用）
6. 建立 SDK Key → 取得明文
7. 產生 User Token → 取得加密字串

Scenarios（E2E_SCENARIOS 逗號分隔選擇，預設全跑）：
- base     ：以 X-SDK-Key + X-User-Token + X-Project-Code 呼叫 deprecated
             /api/v1/model/openrouter/chat（單輪 text），查 /api/v1/usage-logs 驗證有紀錄
- messages ：v2.1.2 功能一 — messages 多輪 /model/chat、同 body /model/chat/stream 串流、
             messages+text 互斥 400、messages=[] 400、temperature 越界 400、
             response_format=json_object 回覆可 json.loads、舊單輪 text 回歸、
             usage log 明細 request_content 含 messages 原樣 + 生成參數
- disable  ：v2.1.2 功能二 — 停用斷權鏈：token 呼叫 200 → admin PATCH is_active=false
             （回應 tokens_revoked=true）→ 同 token 401 → DB 直查 revoked_reason/浮水印
             （可選）→ admin 停用自己 400 → 重新啟用後原 token 仍 401 → 重發 token 200
             → 收尾停用測試帳號（撤銷 token，中和測試資料）

使用方式：
    python -m scripts.e2e_smoke        # 需 dev 環境已啟動（/dev-up）

環境變數：
    BASE_URL                預設 http://localhost:8000（dev compose 對外為 8800）
    ADMIN_ACCOUNT           預設 admin
    ADMIN_PASSWORD          預設 Admin#Pass2026!
    OPENROUTER_KEY          必填（要掛於 TEST 部門作為實打目標；messages/disable 會實際消費）
    TEST_MODEL              預設 anthropic/claude-3.5-haiku
    E2E_SCENARIOS           預設 "base,messages,disable"
    E2E_DATABASE_URL        可選；disable scenario 直查 user_tokens / user_tokens_revocations
                            （未設則退用 DATABASE_URL；皆無或連不上 → 略過 DB 直查，
                            以 API 行為斷言（401 + tokens_revoked）為準）
"""

import json
import os
import sys
import time
from typing import Any
from uuid import uuid4

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_ACCOUNT = os.environ.get("ADMIN_ACCOUNT", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin#Pass2026!")
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY", "")
TEST_MODEL = os.environ.get("TEST_MODEL", "anthropic/claude-3.5-haiku")
E2E_SCENARIOS = {
    s.strip()
    for s in os.environ.get("E2E_SCENARIOS", "base,messages,disable").split(",")
    if s.strip()
}


def _expect_ok(r: httpx.Response, step: str) -> dict[str, Any]:
    if r.status_code // 100 != 2:
        print(f"[FAIL] {step} → HTTP {r.status_code}: {r.text}")
        sys.exit(1)
    body = r.json()
    if not body.get("success", False):
        print(f"[FAIL] {step} → body.success=false: {body}")
        sys.exit(1)
    print(f"[OK]   {step}")
    return body


def _expect_fail(
    r: httpx.Response, step: str, code: int, detail_contains: str
) -> dict[str, Any]:
    """斷言失敗回應：HTTP 狀態碼 + success=false + detail 含指定子字串。"""
    if r.status_code != code:
        print(f"[FAIL] {step} → 預期 HTTP {code}，實得 {r.status_code}: {r.text}")
        sys.exit(1)
    body = r.json()
    if body.get("success") is not False:
        print(f"[FAIL] {step} → 預期 success=false: {body}")
        sys.exit(1)
    detail = str(body.get("detail", ""))
    if detail_contains not in detail:
        print(f"[FAIL] {step} → detail 應含 {detail_contains!r}，實得 {detail!r}")
        sys.exit(1)
    print(f"[OK]   {step}（detail={detail!r}）")
    return body


def _sdk_headers(sdk_key: str, user_token: str, project_code: str) -> dict[str, str]:
    return {
        "X-SDK-Key": sdk_key,
        "X-User-Token": user_token,
        "X-Project-Code": project_code,
    }


# ---------------------------------------------------------------------------
# 供裝（base 步驟 1–7）
# ---------------------------------------------------------------------------


def provision(c: httpx.Client) -> dict[str, Any]:
    """登入 admin 並建立（或冪等重用）部門 / 使用者 / Key / 專案 / Token。"""
    # 1. 登入 admin
    r = c.post(
        "/api/v1/auth/login",
        json={"account": ADMIN_ACCOUNT, "password": ADMIN_PASSWORD},
    )
    body = _expect_ok(r, "login admin")
    admin_uid = body["data"]["user_uid"]

    # 2. 建 TEST 部門
    r = c.post("/api/v1/departments", json={"code": "TEST", "name": "測試部門"})
    if r.status_code == 409:
        # 已存在；查列表拿回 uid
        r2 = c.get("/api/v1/departments", params={"size": 100})
        body = _expect_ok(r2, "list departments (after 409)")
        dept = next(d for d in body["data"]["items"] if d["code"] == "TEST")
    else:
        body = _expect_ok(r, "create TEST department")
        dept = body["data"]
    dept_uid = dept["department_uid"]
    print(f"       dept_uid = {dept_uid}")

    # 3. 建測試使用者（account/password 由後端自動產生；以 email 冪等重用）
    user = _get_or_create_user(
        c,
        step="create test user",
        username="測試使用者",
        email="test.user@df-recycle.com.tw",
        employee_id="T0001",
        dept_uid=dept_uid,
    )
    user_uid = user["user_uid"]
    print(f"       user_uid = {user_uid}")

    # 4. 建 TEST 部門 OpenRouter Key（同名已存在則重用，避免重跑堆疊）
    r = c.get(
        "/api/v1/openrouter-keys", params={"department_uid": dept_uid, "size": 100}
    )
    body = _expect_ok(r, "list openrouter_keys")
    if any(k["name"] == "E2E-Smoke" for k in body["data"]["items"]):
        print("       openrouter_key E2E-Smoke 已存在，重用")
    else:
        r = c.post(
            "/api/v1/openrouter-keys",
            json={"department_uid": dept_uid, "name": "E2E-Smoke", "key": OPENROUTER_KEY},
        )
        _expect_ok(r, "create openrouter_key for TEST")

    # 5. 建 TEST 部門專案（SDK 呼叫必帶 X-Project-Code；同名重用）
    r = c.get("/api/v1/projects", params={"department_uid": dept_uid, "size": 100})
    body = _expect_ok(r, "list projects")
    project = next(
        (p for p in body["data"]["items"] if p["name"] == "E2E-Smoke" and p["is_active"]),
        None,
    )
    if project is None:
        r = c.post(
            "/api/v1/projects",
            json={"department_uid": dept_uid, "name": "E2E-Smoke"},
        )
        body = _expect_ok(r, "create project E2E-Smoke")
        project = body["data"]
    project_code = project["code"]
    print(f"       project_code = {project_code}")

    # 6. 建 SDK Key（明文僅建立時可得，每次執行新建一把）
    r = c.post("/api/v1/sdk-keys", json={"department_uid": dept_uid, "name": "E2E-SDK"})
    body = _expect_ok(r, "create sdk_key")
    sdk_key_plain = body["data"]["key"]
    print(f"       sdk_key_plain prefix = {sdk_key_plain[:22]}...")

    # 7. 產生 User Token（冪等：已有有效 token 則沿用）
    r = c.post(f"/api/v1/users/{user_uid}/tokens")
    body = _expect_ok(r, "generate user token")
    user_token = body["data"]["token"]
    print(f"       user_token length = {len(user_token)}")

    return {
        "admin_uid": admin_uid,
        "dept_uid": dept_uid,
        "user_uid": user_uid,
        "project_code": project_code,
        "sdk_key": sdk_key_plain,
        "user_token": user_token,
    }


def _get_or_create_user(
    c: httpx.Client,
    step: str,
    username: str,
    email: str,
    employee_id: str,
    dept_uid: str,
) -> dict[str, Any]:
    """以 email 冪等取得測試使用者；不存在才建立（account/password 由後端自動產生）。"""
    r = c.get("/api/v1/users", params={"q": email, "size": 50})
    body = _expect_ok(r, f"list users (lookup {email})")
    user = next((u for u in body["data"]["items"] if u["email"] == email), None)
    if user is not None:
        print(f"       使用者 {email} 已存在，重用")
        # 確保狀態/部門符合本次測試前提（上次執行可能停用或掛在別的部門）
        if not user["is_active"] or user["department_uid"] != dept_uid:
            r = c.patch(
                f"/api/v1/users/{user['user_uid']}",
                json={"is_active": True, "department_uid": dept_uid},
            )
            body = _expect_ok(r, f"reset user state ({email})")
            user = body["data"]
        return user
    r = c.post(
        "/api/v1/users",
        json={
            "username": username,
            "role": "user",
            "department_uid": dept_uid,
            "employee_id": employee_id,
            "email": email,
        },
    )
    body = _expect_ok(r, step)
    return body["data"]


# ---------------------------------------------------------------------------
# Scenario: base（v2.1.1 之前既有流程 — deprecated 端點單輪 text + usage-logs）
# ---------------------------------------------------------------------------


def scenario_base(c: httpx.Client, ctx: dict[str, Any]) -> None:
    print("\n=== Scenario: base（單輪 text / deprecated 端點 / usage-logs）===")
    hdrs = _sdk_headers(ctx["sdk_key"], ctx["user_token"], ctx["project_code"])
    with httpx.Client(base_url=BASE_URL, timeout=90) as sdk:
        r = sdk.post(
            "/api/v1/model/openrouter/chat",
            headers=hdrs,
            json={"model": TEST_MODEL, "text": "請用一句話介紹你自己。"},
        )
        body = _expect_ok(r, f"chat completion ({TEST_MODEL})")
        text = body["data"]
        if not isinstance(text, str) or not text.strip():
            print(f"[FAIL] chat 回應 data 應為非空純文字，實得: {body['data']!r}")
            sys.exit(1)
        print(f"       回應片段: {text[:80]!r}")

    # 檢查 usage_logs（admin 身分；背景寫入，輪詢等待）
    total = 0
    for _ in range(10):
        r = c.get("/api/v1/usage-logs", params={"size": 5})
        body = _expect_ok(r, "list usage_logs")
        total = body["data"]["total"]
        if total >= 1:
            break
        time.sleep(1)
    print(f"       usage_logs total = {total}")
    if total < 1:
        print("[FAIL] usage_logs 為 0；背景記帳未寫入")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Scenario: messages（v2.1.2 功能一 — messages 多輪 + 生成參數）
# ---------------------------------------------------------------------------


def scenario_messages(c: httpx.Client, ctx: dict[str, Any]) -> None:
    print("\n=== Scenario: messages（多輪 / stream / 互斥 400 / 生成參數 / 用量明細）===")
    hdrs = _sdk_headers(ctx["sdk_key"], ctx["user_token"], ctx["project_code"])
    marker = f"[e2e-{uuid4().hex[:8]}]"

    # 多輪對話（system + user/assistant 歷史；最後一則以 parts 形式驗證 content 白名單路徑）
    multi_turn = [
        {"role": "system", "content": f"你是簡潔的計算助手 {marker}，只輸出必要內容。"},
        {"role": "user", "content": "我心裡記了一個數字 3。"},
        {"role": "assistant", "content": "好的，我記住了：3。"},
        {
            "role": "user",
            "content": [{"type": "text", "text": "把它加 4，只回覆數字。"}],
        },
    ]

    with httpx.Client(base_url=BASE_URL, timeout=90) as sdk:
        # 1. messages 多輪 → /model/chat 200 + 純文字
        r = sdk.post(
            "/api/v1/model/chat",
            headers=hdrs,
            json={"model": TEST_MODEL, "messages": multi_turn},
        )
        body = _expect_ok(r, "messages multi-turn chat")
        text = body["data"]
        if not isinstance(text, str) or not text.strip():
            print(f"[FAIL] messages chat 回應 data 應為非空純文字，實得: {body['data']!r}")
            sys.exit(1)
        print(f"       回應片段: {text[:80]!r}")
        if "7" not in text:
            print(f"[WARN] 多輪語境推理未回 7（模型行為，非平台缺陷）: {text[:80]!r}")

        # 2. 同 body → /model/chat/stream：收到內容 chunk + [DONE]
        content_chunks = 0
        saw_done = False
        with sdk.stream(
            "POST",
            "/api/v1/model/chat/stream",
            headers=hdrs,
            json={"model": TEST_MODEL, "messages": multi_turn},
        ) as sr:
            if sr.status_code != 200:
                sr.read()
                print(f"[FAIL] messages stream → HTTP {sr.status_code}: {sr.text}")
                sys.exit(1)
            ctype = sr.headers.get("content-type", "")
            if "text/event-stream" not in ctype:
                print(f"[FAIL] stream content-type 應為 text/event-stream，實得 {ctype!r}")
                sys.exit(1)
            for line in sr.iter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[len("data: "):]
                if payload == "[DONE]":
                    saw_done = True
                    break
                obj = json.loads(payload)
                if "error" in obj:
                    print(f"[FAIL] stream 收到 error 事件: {obj}")
                    sys.exit(1)
                if isinstance(obj.get("content"), str) and obj["content"]:
                    content_chunks += 1
        if content_chunks < 1 or not saw_done:
            print(
                f"[FAIL] stream 斷言失敗：content chunks={content_chunks}, [DONE]={saw_done}"
            )
            sys.exit(1)
        print(f"[OK]   messages stream（chunks={content_chunks}, [DONE] 收到）")

        # 3. messages 與 text 同帶 → 400 互斥
        r = sdk.post(
            "/api/v1/model/chat",
            headers=hdrs,
            json={"model": TEST_MODEL, "messages": multi_turn, "text": "hi"},
        )
        _expect_fail(r, "messages + text 互斥", 400, "互斥")

        # 4. messages 空陣列 → 400
        r = sdk.post(
            "/api/v1/model/chat",
            headers=hdrs,
            json={"model": TEST_MODEL, "messages": []},
        )
        _expect_fail(r, "messages 空陣列", 400, "不可為空陣列")

        # 5. temperature 越界（2.5 > 2）→ 400
        r = sdk.post(
            "/api/v1/model/chat",
            headers=hdrs,
            json={"model": TEST_MODEL, "messages": multi_turn, "temperature": 2.5},
        )
        _expect_fail(r, "temperature 越界", 400, "temperature")

        # 6. 生成參數：temperature=0 + max_tokens + response_format=json_object
        #    → 200 且回覆為合法 JSON 字串
        marker_json = f"[e2e-{uuid4().hex[:8]}]"
        json_messages = [
            {
                "role": "system",
                "content": f"你是 JSON 產生器 {marker_json}，只輸出合法 JSON，"
                "不要加任何說明、前後綴或 markdown 圍欄。",
            },
            {
                "role": "user",
                "content": '請以 JSON 物件回覆：{"ok": true, "answer": <3 加 4 的結果>}',
            },
        ]
        gen_params: dict[str, Any] = {
            "temperature": 0,
            "max_tokens": 300,
            "response_format": {"type": "json_object"},
        }
        r = sdk.post(
            "/api/v1/model/chat",
            headers=hdrs,
            json={"model": TEST_MODEL, "messages": json_messages, **gen_params},
        )
        body = _expect_ok(r, "messages + 生成參數（json_object）")
        try:
            parsed = json.loads(body["data"])
        except (TypeError, ValueError):
            print(f"[FAIL] json_object 模式回覆非合法 JSON: {body['data']!r}")
            sys.exit(1)
        print(f"       json.loads OK: {json.dumps(parsed, ensure_ascii=False)[:80]}")

        # 7. 回歸：舊單輪呼叫（只帶 text、無生成參數）於 canonical 端點仍正常
        r = sdk.post(
            "/api/v1/model/chat",
            headers=hdrs,
            json={"model": TEST_MODEL, "text": "請回覆 pong。"},
        )
        body = _expect_ok(r, "單輪 text 回歸（canonical /model/chat）")
        if not isinstance(body["data"], str) or not body["data"].strip():
            print(f"[FAIL] 單輪回歸回應 data 應為非空純文字，實得: {body['data']!r}")
            sys.exit(1)

    # 8. 用量明細：case 6 那筆 log 的 request_content 含 messages 原樣 + 生成參數
    _assert_usage_log_snapshot(c, marker_json, json_messages, gen_params)


def _assert_usage_log_snapshot(
    c: httpx.Client,
    marker: str,
    sent_messages: list[dict[str, Any]],
    gen_params: dict[str, Any],
) -> None:
    """輪詢 usage-logs（背景寫入），以 system 訊息中的 marker 找到該筆並驗證快照。"""
    rc: dict[str, Any] | None = None
    for _ in range(15):
        r = c.get("/api/v1/usage-logs", params={"size": 10, "model": TEST_MODEL})
        body = _expect_ok(r, "list usage_logs (messages)")
        for item in body["data"]["items"]:
            rd = c.get(f"/api/v1/usage-logs/{item['usage_log_uid']}")
            detail = _expect_ok(rd, f"get usage_log detail #{item['pid']}")["data"]
            candidate = detail.get("request_content") or {}
            msgs = candidate.get("messages")
            if isinstance(msgs, list) and any(
                isinstance(m.get("content"), str) and marker in m["content"] for m in msgs
            ):
                rc = candidate
                break
        if rc is not None:
            break
        time.sleep(1)
    if rc is None:
        print(f"[FAIL] 用量明細找不到帶 marker {marker} 的 messages 紀錄（背景記帳未寫入？）")
        sys.exit(1)
    if rc.get("messages") != sent_messages:
        print(
            "[FAIL] request_content.messages 與送出內容不一致\n"
            f"       expected: {sent_messages}\n"
            f"       actual:   {rc.get('messages')}"
        )
        sys.exit(1)
    for key, expected in gen_params.items():
        if rc.get(key) != expected:
            print(f"[FAIL] request_content.{key} 應為 {expected!r}，實得 {rc.get(key)!r}")
            sys.exit(1)
    print("[OK]   usage_log 明細：messages 原樣快照 + 生成參數（temperature/max_tokens/response_format）")


# ---------------------------------------------------------------------------
# Scenario: disable（v2.1.2 功能二 — 停用斷權鏈）
# ---------------------------------------------------------------------------


def scenario_disable(c: httpx.Client, ctx: dict[str, Any]) -> None:
    print("\n=== Scenario: disable（停用斷權鏈）===")
    dept_uid = ctx["dept_uid"]

    # 專用測試使用者（不與 base/messages 共用，避免撤銷互相干擾；以 email 冪等重用）
    user = _get_or_create_user(
        c,
        step="create disable-test user",
        username="E2E 停用測試",
        email="e2e.disable@df-recycle.com.tw",
        employee_id="T9998",
        dept_uid=dept_uid,
    )
    user_uid = user["user_uid"]
    print(f"       disable-test user_uid = {user_uid}")

    r = c.post(f"/api/v1/users/{user_uid}/tokens")
    body = _expect_ok(r, "generate token (disable-test)")
    old_token = body["data"]["token"]

    hdrs = _sdk_headers(ctx["sdk_key"], old_token, ctx["project_code"])
    with httpx.Client(base_url=BASE_URL, timeout=90) as sdk:
        # 1. 停用前：token 有效 → SDK 呼叫 200
        r = sdk.post(
            "/api/v1/model/chat",
            headers=hdrs,
            json={"model": TEST_MODEL, "text": "請回覆 pong。", "max_tokens": 16},
        )
        _expect_ok(r, "停用前 SDK 呼叫（token 有效）")

        # 2. admin 停用 → 200 且 tokens_revoked=true
        r = c.patch(f"/api/v1/users/{user_uid}", json={"is_active": False})
        body = _expect_ok(r, "admin PATCH is_active=false")
        if body["data"].get("tokens_revoked") is not True:
            print(f"[FAIL] 停用回應 tokens_revoked 應為 true: {body['data']}")
            sys.exit(1)
        if body["data"].get("is_active") is not False:
            print(f"[FAIL] 停用回應 is_active 應為 false: {body['data']}")
            sys.exit(1)

        # 3. 同 token SDK 呼叫 → 401（驗證鏈擋下，未達下游、不消費）
        r = sdk.post(
            "/api/v1/model/chat",
            headers=hdrs,
            json={"model": TEST_MODEL, "text": "ping"},
        )
        _expect_fail(r, "停用後同 token SDK 呼叫", 401, "unauthorized")

        # 4. DB 直查（可選）：user_tokens 標 revoked + user_tokens_revocations 浮水印
        _check_disable_db_state(user_uid)

        # 5. admin 停用自己 → 400 cannot_disable_self
        r = c.patch(f"/api/v1/users/{ctx['admin_uid']}", json={"is_active": False})
        _expect_fail(r, "admin 停用自己", 400, "cannot_disable_self")

        # 6. 重新啟用 → 原 token 仍 401（不自動復活）
        r = c.patch(f"/api/v1/users/{user_uid}", json={"is_active": True})
        body = _expect_ok(r, "admin PATCH is_active=true")
        if body["data"].get("tokens_revoked") is not False:
            print(f"[FAIL] 重新啟用不應觸發撤銷（tokens_revoked 應為 false）: {body['data']}")
            sys.exit(1)
        r = sdk.post(
            "/api/v1/model/chat",
            headers=hdrs,
            json={"model": TEST_MODEL, "text": "ping"},
        )
        _expect_fail(r, "重新啟用後原 token 仍失效", 401, "unauthorized")

        # 7. 重新產生 token → 新 token 可正常呼叫
        r = c.post(f"/api/v1/users/{user_uid}/tokens")
        body = _expect_ok(r, "regenerate token")
        new_token = body["data"]["token"]
        if new_token == old_token:
            print("[FAIL] 重發 token 不應與已撤銷的舊 token 相同")
            sys.exit(1)
        r = sdk.post(
            "/api/v1/model/chat",
            headers=_sdk_headers(ctx["sdk_key"], new_token, ctx["project_code"]),
            json={"model": TEST_MODEL, "text": "請回覆 pong。", "max_tokens": 16},
        )
        _expect_ok(r, "新 token SDK 呼叫")

    # 收尾：停用測試帳號（撤銷 token，中和測試資料；下次執行會自動重新啟用）
    r = c.patch(f"/api/v1/users/{user_uid}", json={"is_active": False})
    _expect_ok(r, "cleanup: 停用 disable-test 使用者")


def _check_disable_db_state(user_uid: str) -> None:
    """直查 DB 驗證停用撤銷落地（可選；連不上不視為失敗，以 API 行為斷言為準）。

    - user_tokens：最新一筆 revoked_at 非空 + revoked_reason='user_disabled'
    - user_tokens_revocations：reason='user_disabled' 浮水印 ≥ 1 筆
    """
    db_url = os.environ.get("E2E_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
    if not db_url:
        print(
            "[SKIP] DB 直查（revoked_reason / 浮水印）：未設 E2E_DATABASE_URL / DATABASE_URL；"
            "以 API 行為斷言（401 + tokens_revoked=true）為準"
        )
        return
    try:
        from sqlalchemy import create_engine
        from sqlalchemy import text as sql_text
    except ImportError:
        print("[SKIP] DB 直查：環境無 sqlalchemy，略過")
        return

    sync_url = db_url.replace("+asyncpg", "+psycopg")
    # dev compose 內 DATABASE_URL host 為 postgres（容器網路）；host 端退用對外埠 5533。
    candidates = [sync_url]
    if "@postgres:" in sync_url:
        candidates.append(sync_url.replace("@postgres:5432", "@localhost:5533"))
    last_err: Exception | None = None
    for url in candidates:
        try:
            engine = create_engine(url)
            with engine.connect() as conn:
                row = conn.execute(
                    sql_text(
                        "SELECT revoked_at, revoked_reason FROM user_tokens "
                        "WHERE user_uid = CAST(:u AS uuid) ORDER BY pid DESC LIMIT 1"
                    ),
                    {"u": user_uid},
                ).first()
                watermarks = conn.execute(
                    sql_text(
                        "SELECT COUNT(*) FROM user_tokens_revocations "
                        "WHERE user_uid = CAST(:u AS uuid) AND reason = 'user_disabled'"
                    ),
                    {"u": user_uid},
                ).scalar()
            engine.dispose()
        except Exception as exc:  # noqa: BLE001 — 連線失敗僅降級略過，不中斷 smoke
            last_err = exc
            continue
        if row is None or row[0] is None or row[1] != "user_disabled":
            print(f"[FAIL] user_tokens 未標記 revoked（revoked_reason=user_disabled）: {row}")
            sys.exit(1)
        if not watermarks:
            print("[FAIL] user_tokens_revocations 無 reason='user_disabled' 浮水印")
            sys.exit(1)
        print(
            "[OK]   DB 直查：user_tokens revoked_reason='user_disabled' + "
            f"浮水印 {watermarks} 筆"
        )
        return
    print(f"[SKIP] DB 直查：連線失敗（{last_err}）；以 API 行為斷言為準")


# ---------------------------------------------------------------------------


def main() -> None:
    if not OPENROUTER_KEY:
        print("[FAIL] 環境變數 OPENROUTER_KEY 未設定，無法建立 TEST 部門 Key")
        sys.exit(1)
    unknown = E2E_SCENARIOS - {"base", "messages", "disable"}
    if unknown:
        print(f"[FAIL] E2E_SCENARIOS 含未知 scenario: {sorted(unknown)}")
        sys.exit(1)

    with httpx.Client(base_url=BASE_URL, timeout=60) as c:
        ctx = provision(c)
        if "base" in E2E_SCENARIOS:
            scenario_base(c, ctx)
        if "messages" in E2E_SCENARIOS:
            scenario_messages(c, ctx)
        if "disable" in E2E_SCENARIOS:
            scenario_disable(c, ctx)

    print(f"\n[ALL OK] 全部流程通過（scenarios: {', '.join(sorted(E2E_SCENARIOS))}）🎉")


if __name__ == "__main__":
    main()
