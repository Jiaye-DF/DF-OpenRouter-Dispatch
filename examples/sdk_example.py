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
) -> dict:
    """呼叫代理端點;成功回 OpenRouter 標準 chat completion 物件。

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

    # 後端統一回應結構:{"success": bool, "code": int, "data": ..., "detail": str}
    try:
        body = resp.json()
    except Exception:
        raise RuntimeError(f"HTTP {resp.status_code} · 非 JSON 回應: {resp.text[:200]}")

    if not body.get("success"):
        raise RuntimeError(f"HTTP {body.get('code')} · {body.get('detail')}")
    return body["data"]


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

    prompt = sys.argv[1] if len(sys.argv) > 1 else "hello"

    print(f"→ POST {api_base}/api/v1/model/chat")
    print(f"  model:   {model}")
    print(f"  project: {project_code}")
    print(f"  prompt:  {prompt}")
    print()

    try:
        data = chat(
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

    # OpenRouter 標準回應結構:choices[0].message.content
    reply = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})

    print("[OK] 回應:")
    print(reply)
    print()
    if usage:
        print(
            f"  tokens: prompt={usage.get('prompt_tokens', 0)} "
            f"completion={usage.get('completion_tokens', 0)} "
            f"total={usage.get('total_tokens', 0)} "
            f"cost=${usage.get('cost', 0)}"
        )


if __name__ == "__main__":
    main()
