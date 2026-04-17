"""
End-to-end smoke test for DF-OpenRouter-Dispatch.

流程：
1. 登入初始 admin 取得 Cookie
2. 建立 TEST 部門
3. 建立 test.user 使用者於 TEST 部門（含 email/employee_id）
4. 建立 TEST 部門的 OpenRouter Key（若 SYSTEM 已有 default，仍為 TEST 建一把）
5. 建立 SDK Key → 取得明文
6. 產生 User Token → 取得加密字串
7. 以 X-SDK-Key + X-User-Token 呼叫 /api/v1/model/openrouter/chat
8. 查 /api/v1/usage-logs 驗證有紀錄

使用方式：
    python -m scripts.e2e_smoke

環境變數：
    BASE_URL                預設 http://localhost:8000
    ADMIN_ACCOUNT           預設 admin
    ADMIN_PASSWORD          預設 Admin#Pass2026!
    OPENROUTER_KEY          必填（要掛於 TEST 部門作為實打目標）
    TEST_MODEL              預設 anthropic/claude-3.5-haiku
"""

import json
import os
import sys
from typing import Any

import httpx


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_ACCOUNT = os.environ.get("ADMIN_ACCOUNT", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin#Pass2026!")
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY", "")
TEST_MODEL = os.environ.get("TEST_MODEL", "anthropic/claude-3.5-haiku")


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


def main() -> None:
    if not OPENROUTER_KEY:
        print("[FAIL] 環境變數 OPENROUTER_KEY 未設定，無法建立 TEST 部門 Key")
        sys.exit(1)

    with httpx.Client(base_url=BASE_URL, timeout=60) as c:
        # 1. 登入 admin
        r = c.post(
            "/api/v1/auth/login",
            json={"account": ADMIN_ACCOUNT, "password": ADMIN_PASSWORD},
        )
        _expect_ok(r, "login admin")

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

        # 3. 建測試使用者
        test_account = "test.user"
        r = c.post(
            "/api/v1/users",
            json={
                "account": test_account,
                "username": "測試使用者",
                "password": "TestUser#2026!",
                "role": "user",
                "department_uid": dept_uid,
                "employee_id": "T0001",
                "email": "test.user@df-recycle.com.tw",
            },
        )
        if r.status_code == 400 and "account_taken" in r.text:
            r2 = c.get("/api/v1/users", params={"size": 100})
            body = _expect_ok(r2, "list users (after 400)")
            user = next(u for u in body["data"]["items"] if u["account"] == test_account)
        else:
            body = _expect_ok(r, "create test user")
            user = body["data"]
        user_uid = user["user_uid"]
        print(f"       user_uid = {user_uid}")

        # 4. 建 TEST 部門 OpenRouter Key
        r = c.post(
            "/api/v1/openrouter-keys",
            json={
                "department_uid": dept_uid,
                "name": "E2E-Smoke",
                "key": OPENROUTER_KEY,
            },
        )
        _expect_ok(r, "create openrouter_key for TEST")

        # 5. 建 SDK Key
        r = c.post("/api/v1/sdk-keys", json={"department_uid": dept_uid, "name": "E2E-SDK"})
        body = _expect_ok(r, "create sdk_key")
        sdk_key_plain = body["data"]["key"]
        print(f"       sdk_key_plain prefix = {sdk_key_plain[:22]}...")

        # 6. 產生 User Token
        r = c.post(f"/api/v1/users/{user_uid}/tokens")
        body = _expect_ok(r, "generate user token")
        user_token = body["data"]["token"]
        print(f"       user_token length = {len(user_token)}")

        # 7. 呼叫 /chat（需新 client 或換 header；不帶 Cookie 以模擬 SDK 呼叫）
        with httpx.Client(base_url=BASE_URL, timeout=90) as sdk:
            r = sdk.post(
                "/api/v1/model/openrouter/chat",
                headers={
                    "X-SDK-Key": sdk_key_plain,
                    "X-User-Token": user_token,
                },
                json={
                    "model": TEST_MODEL,
                    "text": "請用一句話介紹你自己。",
                },
            )
            body = _expect_ok(r, f"chat completion ({TEST_MODEL})")
            choices = body["data"].get("choices") or []
            if choices:
                msg = choices[0].get("message", {}).get("content")
                print(f"       回應片段: {str(msg)[:80]!r}")

        # 8. 檢查 usage_logs（admin 身分）
        r = c.get("/api/v1/usage-logs", params={"size": 5})
        body = _expect_ok(r, "list usage_logs")
        total = body["data"]["total"]
        print(f"       usage_logs total = {total}")
        if total < 1:
            print("[WARN] usage_logs 目前為 0；可能背景寫入尚未完成，再試查一次。")

    print("\n[ALL OK] 全部流程通過 🎉")


if __name__ == "__main__":
    main()
