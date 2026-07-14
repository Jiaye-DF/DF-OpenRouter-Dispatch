"""DF-OpenRouter-Dispatch · SDK 使用者範例(Python / httpx)

最小可用範例 — 帶 3 個必要 header 呼叫代理端點 `/api/v1/model/chat`。
本檔案內容對齊 docs/INTEGRATION.md;可直接複製到你的專案改造。

────────────────────────────────────────────────────────────────────
前置:
  pip install httpx

設定(透過環境變數注入,不要把憑證寫死於程式碼):
  DFOR_API_BASE       例: https://df-it-openrouter-dispatch-api.it.zerozero.tw
                          或 http://localhost:8800(本機 dev)
  DFOR_SDK_KEY        管理員發放的 X-SDK-Key 明文
  DFOR_USER_TOKEN     管理員發放的 X-User-Token 加密字串
  DFOR_PROJECT_CODE   後台「專案管理」頁顯示的「代碼」欄
  DFOR_MODEL          (選填) 模型 id,預設 openai/gpt-4o-mini

兩種注入方式擇一:
  (a) 寫入專案根目錄 `.env`(已被 .gitignore 排除),本檔會自動載入。
  (b) shell 自行 export / $env: 設定後再執行。
  注意:已存在於 process 環境的變數優先,.env 不會覆蓋。

執行:
  python examples/sdk_example.py "你想問的問題"
  # 或不帶參數,使用預設 prompt:
  python examples/sdk_example.py
  # messages 多輪對話 + 生成參數範例(v2.1.2):
  python examples/sdk_example.py --messages "好,幫我總結一下目前狀態"
  # response_format 結構化輸出(json_object)範例(v2.1.2):
  python examples/sdk_example.py --json "列出台灣三大城市與人口"
────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx


def _load_dotenv() -> None:
    """從專案根 `.env` 載入變數至 os.environ(已存在者不覆蓋)。"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def chat(
    *,
    api_base: str,
    sdk_key: str,
    user_token: str,
    project_code: str,
    model: str,
    text: str,
) -> str:
    """呼叫代理端點;成功回模型回答的純文字(後端已精簡 response 為單一字串)。

    失敗時 raise RuntimeError,訊息含 HTTP code 與後端 detail。
    """
    resp = httpx.post(
        f"{api_base.rstrip('/')}/api/v1/model/chat",
        headers={
            "X-SDK-Key": sdk_key,
            "X-User-Token": user_token,
            "X-Project-Code": project_code,
            "Content-Type": "application/json",
        },
        json={"model": model, "text": text},
        timeout=60,
    )

    # 後端統一回應結構:{"success": bool, "code": int, "data": str, "detail": str}
    try:
        body = resp.json()
    except Exception:
        raise RuntimeError(f"HTTP {resp.status_code} · 非 JSON 回應: {resp.text[:200]}")

    if not body.get("success"):
        raise RuntimeError(f"HTTP {body.get('code')} · {body.get('detail')}")
    return body["data"] or ""


def chat_messages(
    *,
    api_base: str,
    sdk_key: str,
    user_token: str,
    project_code: str,
    model: str,
    messages: list[dict],
    temperature: float | None = None,
    max_tokens: int | None = None,
    response_format: dict | None = None,
) -> str:
    """messages 多輪呼叫範例(v2.1.2)——自帶 system prompt / 對話歷史。

    - `messages`:`[{"role": ..., "content": ...}]`;role 只收 system / user /
      assistant,content 為字串或 parts 陣列(text / image_url / file)。
      與 text / images / files **互斥**,擇一提供(同時帶回 400)。
    - 生成參數(選填,單輪模式同樣可帶):`temperature`(0–2)/
      `max_tokens`(≥1)/ `response_format`(如 {"type": "json_object"});
      未帶(None)不放進 body,走模型預設值。
    - 其餘生成參數(top_p / stop / penalties 等)不開放,請勿帶入。

    失敗時 raise RuntimeError,訊息含 HTTP code 與後端 detail。
    """
    payload: dict = {"model": model, "messages": messages}
    # 生成參數:有帶才放進 body;None 一律不出現(走模型預設)
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if response_format is not None:
        payload["response_format"] = response_format

    resp = httpx.post(
        f"{api_base.rstrip('/')}/api/v1/model/chat",
        headers={
            "X-SDK-Key": sdk_key,
            "X-User-Token": user_token,
            "X-Project-Code": project_code,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )

    try:
        body = resp.json()
    except Exception:
        raise RuntimeError(f"HTTP {resp.status_code} · 非 JSON 回應: {resp.text[:200]}")

    if not body.get("success"):
        raise RuntimeError(f"HTTP {body.get('code')} · {body.get('detail')}")
    return body["data"] or ""


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"[ERROR] 環境變數 {name} 未設定(請參考檔案頂部說明)", file=sys.stderr)
        sys.exit(2)
    return val


def main() -> None:
    _load_dotenv()
    api_base     = os.environ.get("DFOR_API_BASE", "http://localhost:8800")
    sdk_key      = _require_env("DFOR_SDK_KEY")
    user_token   = _require_env("DFOR_USER_TOKEN")
    project_code = _require_env("DFOR_PROJECT_CODE")
    model        = os.environ.get("DFOR_MODEL", "openai/gpt-4o-mini")

    mode   = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("--messages", "--json") else None
    prompt = sys.argv[2] if mode and len(sys.argv) > 2 else (sys.argv[1] if not mode and len(sys.argv) > 1 else "hello")

    print(f"→ POST {api_base}/api/v1/model/chat")
    print(f"  model:   {model}")
    print(f"  project: {project_code}")
    print(f"  mode:    {mode or '單輪 text'}")
    print(f"  prompt:  {prompt}")
    print()

    try:
        if mode == "--messages":
            # v2.1.2 messages 多輪:system prompt + 對話歷史 + 本輪提問,
            # 並示範帶生成參數(temperature / max_tokens)。
            reply = chat_messages(
                api_base=api_base,
                sdk_key=sdk_key,
                user_token=user_token,
                project_code=project_code,
                model=model,
                messages=[
                    {"role": "system", "content": "你是客服助理,回答一律使用繁體中文。"},
                    {"role": "user", "content": "上次說到哪?"},
                    {"role": "assistant", "content": "說到出貨進度。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=256,
            )
        elif mode == "--json":
            # v2.1.2 response_format 結構化輸出:json_object 讓模型回合法 JSON
            # 字串(prompt 需明確要求回 JSON);回應可直接 json.loads 解析。
            reply = chat_messages(
                api_base=api_base,
                sdk_key=sdk_key,
                user_token=user_token,
                project_code=project_code,
                model=model,
                messages=[{"role": "user", "content": f"{prompt}。請以 JSON 物件格式回答。"}],
                temperature=0.2,
                max_tokens=256,
                response_format={"type": "json_object"},
            )
        else:
            reply = chat(
                api_base=api_base,
                sdk_key=sdk_key,
                user_token=user_token,
                project_code=project_code,
                model=model,
                text=prompt,
            )
    except RuntimeError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        sys.exit(1)

    # 後端已精簡為 data: <字串>;usage / cost / id 等只在後台 dashboard 看得到。
    print("[OK] 回應:")
    print(reply)


if __name__ == "__main__":
    main()
