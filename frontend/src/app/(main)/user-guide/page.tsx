"use client";

import * as React from "react";
import { Check, Copy } from "lucide-react";
import { PageTitle } from "@/components/common/PageTitle";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { cn } from "@/lib/utils/cn";

// 測試 / 正式環境的 API Base URL ——「呼叫環境」表格與範例程式碼會自動套用(範例以正式環境為準)。
const TEST_API_BASE = "https://df-it-openrouter-dispatch-stage-api.it.zerozero.tw";
const PROD_API_BASE = "https://df-it-openrouter-dispatch-api.it.zerozero.tw";

// 「呼叫環境」表格顯示用
const API_ENVIRONMENTS: { label: string; base: string }[] = [
  { label: "測試環境", base: TEST_API_BASE },
  { label: "正式環境", base: PROD_API_BASE },
];

// 範例程式碼顯示用的 base:正式優先 → 測試 → 佔位字串
const API_BASE = (
  PROD_API_BASE ||
  TEST_API_BASE ||
  "https://<正式站網址>"
).replace(/\/$/, "");
const CHAT_URL = `${API_BASE}/api/v1/model/chat`;
const STREAM_URL = `${API_BASE}/api/v1/model/chat/stream`;
const MODELS_URL = `${API_BASE}/api/v1/allowed/models`;

function CodeBlock({
  code,
  language,
  className,
}: {
  code: string;
  language?: string;
  className?: string;
}) {
  const [copied, setCopied] = React.useState(false);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* 忽略 */
    }
  };
  return (
    <div
      className={cn(
        "relative group rounded-xl border border-border bg-muted/40",
        className
      )}
    >
      {language && (
        <div className="px-4 py-1.5 text-sm text-muted-foreground border-b border-border font-mono">
          {language}
        </div>
      )}
      <pre className="overflow-x-auto px-4 py-3 text-sm font-mono leading-relaxed">
        <code>{code}</code>
      </pre>
      <button
        type="button"
        onClick={onCopy}
        aria-label="複製"
        className={cn(
          "absolute top-2 right-2 flex items-center gap-1 rounded-lg border border-border bg-background px-2 py-1 text-sm",
          "opacity-0 group-hover:opacity-100 hover:cursor-pointer transition-opacity"
        )}
      >
        {copied ? (
          <>
            <Check className="h-3.5 w-3.5 text-emerald-600" />
            已複製
          </>
        ) : (
          <>
            <Copy className="h-3.5 w-3.5" />
            複製
          </>
        )}
      </button>
    </div>
  );
}

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-20">
      <h2 className="text-lg font-semibold mb-3">{title}</h2>
      <Card>
        <CardContent className="pt-6 flex flex-col gap-4 text-sm leading-relaxed">
          {children}
        </CardContent>
      </Card>
    </section>
  );
}

const CURL_EXAMPLE = `curl -X POST '${CHAT_URL}' \\
  -H 'Content-Type: application/json' \\
  -H 'X-SDK-Key: ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \\
  -H 'X-User-Token: <admin 發放的 User Token>' \\
  -H 'X-Project-Code: 53299897503322112' \\
  -d '{
    "model": "google/gemini-2.5-flash",
    "text": "用一句話介紹台灣"
  }'`;

const PYTHON_EXAMPLE = `import httpx

API_URL = "${CHAT_URL}"
SDK_KEY = "ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
USER_TOKEN = "<admin 發放的 User Token>"
PROJECT_CODE = "<admin 後台「專案管理」頁複製的代碼>"

def chat(model: str, text: str) -> dict:
    resp = httpx.post(
        API_URL,
        headers={
            "X-SDK-Key": SDK_KEY,
            "X-User-Token": USER_TOKEN,
            "X-Project-Code": PROJECT_CODE,
            "Content-Type": "application/json",
        },
        json={"model": model, "text": text},
        timeout=60,
    )
    resp.raise_for_status()
    body = resp.json()
    if not body["success"]:
        raise RuntimeError(f"{body['code']} {body['detail']}")
    return body["data"]

if __name__ == "__main__":
    answer = chat("google/gemini-2.5-flash", "用一句話介紹台灣")
    print(answer)`;

// Web 搜尋範例:查今日美元換台幣即時匯率(帶 openrouter:web_search 工具)
const CURL_WEBSEARCH_EXAMPLE = `curl -X POST '${CHAT_URL}' \\
  -H 'Content-Type: application/json' \\
  -H 'X-SDK-Key: ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \\
  -H 'X-User-Token: <admin 發放的 User Token>' \\
  -H 'X-Project-Code: 53299897503322112' \\
  -d '{
    "model": "google/gemini-2.5-flash",
    "text": "今天 1 美元可以換多少新台幣?請用最新即時匯率回答,並標註資料來源與查詢時間。",
    "tools": [{ "type": "openrouter:web_search" }]
  }'`;

const PYTHON_WEBSEARCH_EXAMPLE = `import httpx

API_URL = "${CHAT_URL}"
SDK_KEY = "ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
USER_TOKEN = "<admin 發放的 User Token>"
PROJECT_CODE = "<admin 後台「專案管理」頁複製的代碼>"

def chat_with_web_search(model: str, text: str) -> dict:
    resp = httpx.post(
        API_URL,
        headers={
            "X-SDK-Key": SDK_KEY,
            "X-User-Token": USER_TOKEN,
            "X-Project-Code": PROJECT_CODE,
            "Content-Type": "application/json",
        },
        # 帶 tools 啟用 OpenRouter server 端 web search;回應仍為純文字
        json={
            "model": model,
            "text": text,
            "tools": [{"type": "openrouter:web_search"}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    body = resp.json()
    if not body["success"]:
        raise RuntimeError(f"{body['code']} {body['detail']}")
    return body["data"]

if __name__ == "__main__":
    answer = chat_with_web_search(
        "google/gemini-2.5-flash",
        "今天 1 美元可以換多少新台幣?請用最新即時匯率回答,並標註資料來源與查詢時間。",
    )
    print(answer)`;

// 檔案上傳範例(PDF)—— 遠端 URL 版,可直接 copy 測試
const CURL_FILE_EXAMPLE = `curl -X POST '${CHAT_URL}' \\
  -H 'Content-Type: application/json' \\
  -H 'X-SDK-Key: ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \\
  -H 'X-User-Token: <admin 發放的 User Token>' \\
  -H 'X-Project-Code: 53299897503322112' \\
  -d '{
    "model": "google/gemini-2.5-flash",
    "text": "請用三點摘要這份文件的重點",
    "files": [
      {
        "filename": "bitcoin.pdf",
        "file_data": "https://bitcoin.org/bitcoin.pdf"
      }
    ]
  }'`;

// 檔案上傳範例(PDF)—— Python:讀本機 PDF 轉 base64 data URL
const PYTHON_FILE_EXAMPLE = `import base64
from pathlib import Path

import httpx

API_URL = "${CHAT_URL}"
SDK_KEY = "ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
USER_TOKEN = "<admin 發放的 User Token>"
PROJECT_CODE = "<admin 後台「專案管理」頁複製的代碼>"

def to_data_url(path: str) -> str:
    """把本機 PDF 轉成 base64 data URL。"""
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    return f"data:application/pdf;base64,{b64}"

def chat_with_file(model: str, text: str, file_path: str) -> dict:
    resp = httpx.post(
        API_URL,
        headers={
            "X-SDK-Key": SDK_KEY,
            "X-User-Token": USER_TOKEN,
            "X-Project-Code": PROJECT_CODE,
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "text": text,
            "files": [
                {"filename": Path(file_path).name, "file_data": to_data_url(file_path)}
            ],
        },
        timeout=120,  # 檔案較大,逾時放寬
    )
    resp.raise_for_status()
    body = resp.json()
    if not body["success"]:
        raise RuntimeError(f"{body['code']} {body['detail']}")
    return body["data"]

if __name__ == "__main__":
    answer = chat_with_file(
        "google/gemini-2.5-flash",
        "請用三點摘要這份文件的重點",
        "report.pdf",
    )
    print(answer)`;

// 串流(SSE)範例 —— /model/chat/stream
const CURL_STREAM_EXAMPLE = `curl -N -X POST '${STREAM_URL}' \\
  -H 'Content-Type: application/json' \\
  -H 'X-SDK-Key: ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \\
  -H 'X-User-Token: <admin 發放的 User Token>' \\
  -H 'X-Project-Code: 53299897503322112' \\
  -d '{"model":"anthropic/claude-3.5-haiku","text":"用三句話介紹台灣"}'`;

// Windows PowerShell:用 curl.exe(行尾為 PowerShell 續行的反引號)
const CURL_STREAM_PWSH_EXAMPLE = `curl.exe -N -X POST '${STREAM_URL}' \`
  -H 'Content-Type: application/json' \`
  -H 'X-SDK-Key: ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \`
  -H 'X-User-Token: <admin 發放的 User Token>' \`
  -H 'X-Project-Code: 53299897503322112' \`
  -d '{\\"model\\":\\"anthropic/claude-3.5-haiku\\",\\"text\\":\\"用三句話介紹台灣\\"}'`;

const STREAM_OUTPUT_EXAMPLE = `data: {"id":"gen-1781149616-d2ysVJPcqDRdHy6sxYBm","content":"以"}

data: {"id":"gen-1781149616-d2ysVJPcqDRdHy6sxYBm","content":"下是用"}

data: {"id":"gen-1781149616-d2ysVJPcqDRdHy6sxYBm","content":"三句話介紹台灣："}

data: [DONE]`;

const PYTHON_STREAM_EXAMPLE = `import json
import httpx

API_URL = "${STREAM_URL}"
SDK_KEY = "ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
USER_TOKEN = "<admin 發放的 User Token>"
PROJECT_CODE = "<admin 後台「專案管理」頁複製的代碼>"

def chat_stream(model: str, text: str):
    headers = {
        "X-SDK-Key": SDK_KEY,
        "X-User-Token": USER_TOKEN,
        "X-Project-Code": PROJECT_CODE,
        "Content-Type": "application/json",
    }
    with httpx.stream(
        "POST", API_URL, headers=headers,
        json={"model": model, "text": text}, timeout=None,
    ) as resp:
        # 開串流前的錯誤仍是一般 JSON,先擋下來
        if "text/event-stream" not in resp.headers.get("content-type", ""):
            raise RuntimeError(f"{resp.status_code} {resp.read().decode()}")
        for line in resp.iter_lines():
            if not line.startswith("data:"):
                continue  # 略過空行 / keep-alive 註解
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            chunk = json.loads(data)          # 簡化格式:{"id": ..., "content": ...}
            if "error" in chunk:
                raise RuntimeError(chunk["error"])
            print(chunk.get("content", ""), end="", flush=True)  # 逐字輸出
    print()

if __name__ == "__main__":
    chat_stream("anthropic/claude-3.5-haiku", "用三句話介紹台灣")`;

const IMAGE_EXAMPLE = `{
  "model": "google/gemini-2.5-flash",
  "text": "請描述這張圖片",
  "images": [
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...",
    "https://example.com/photo.jpg"
  ]
}`;

const TOOLS_EXAMPLE = `{
  "model": "google/gemini-2.5-flash",
  "text": "今天台積電(2330)的最新股價與相關新聞?",
  "tools": [{ "type": "openrouter:web_search" }]
}`;

const FILE_EXAMPLE = `{
  "model": "google/gemini-2.5-flash",
  "text": "請用三點摘要這份文件的重點",
  "files": [
    {
      "filename": "report.pdf",
      "file_data": "data:application/pdf;base64,JVBERi0xLjcK..."
    }
  ]
}`;

// 多輪對話(messages)Request 範例 —— v2.1.2
const MESSAGES_EXAMPLE = `{
  "model": "google/gemini-2.5-flash",
  "messages": [
    { "role": "system", "content": "你是客服助理,回答一律使用繁體中文。" },
    { "role": "user", "content": "上次說到哪?" },
    { "role": "assistant", "content": "說到出貨進度。" },
    { "role": "user", "content": [
      { "type": "text", "text": "看一下這張圖與檔案,幫我確認狀態" },
      { "type": "image_url", "image_url": { "url": "data:image/png;base64,iVBORw0KGgo..." } },
      { "type": "file", "file": { "filename": "出貨單.pdf", "file_data": "data:application/pdf;base64,JVBERi0..." } }
    ] }
  ]
}`;

// 生成參數 Request 範例 —— v2.1.2(json_object 結構化輸出)
const GENPARAMS_EXAMPLE = `{
  "model": "google/gemini-2.5-flash",
  "text": "抽取:『7/20 前交付 100 件到台中廠』的日期、數量、地點,以 JSON 回覆(鍵:date, qty, location)",
  "temperature": 0.2,
  "max_tokens": 256,
  "response_format": { "type": "json_object" }
}`;

// 多輪對話範例 —— curl
const CURL_MESSAGES_EXAMPLE = `curl -X POST '${CHAT_URL}' \\
  -H 'Content-Type: application/json' \\
  -H 'X-SDK-Key: ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' \\
  -H 'X-User-Token: <admin 發放的 User Token>' \\
  -H 'X-Project-Code: 53299897503322112' \\
  -d '{
    "model": "google/gemini-2.5-flash",
    "messages": [
      { "role": "system", "content": "你是客服助理,回答一律使用繁體中文。" },
      { "role": "user", "content": "我上週訂的貨到哪了?" },
      { "role": "assistant", "content": "請提供訂單編號,我幫您查詢。" },
      { "role": "user", "content": "訂單編號是 A12345" }
    ],
    "temperature": 0.3
  }'`;

// 多輪對話範例 —— Python
const PYTHON_MESSAGES_EXAMPLE = `import httpx

API_URL = "${CHAT_URL}"
SDK_KEY = "ordsk_xxxxxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
USER_TOKEN = "<admin 發放的 User Token>"
PROJECT_CODE = "<admin 後台「專案管理」頁複製的代碼>"

def chat_messages(model: str, messages: list[dict], temperature: float | None = None) -> str:
    payload = {"model": model, "messages": messages}
    if temperature is not None:      # 未帶就不放進 body,走模型預設
        payload["temperature"] = temperature
    resp = httpx.post(
        API_URL,
        headers={
            "X-SDK-Key": SDK_KEY,
            "X-User-Token": USER_TOKEN,
            "X-Project-Code": PROJECT_CODE,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    body = resp.json()
    if not body["success"]:
        raise RuntimeError(f"{body['code']} {body['detail']}")
    return body["data"]

if __name__ == "__main__":
    history = [
        {"role": "system", "content": "你是客服助理,回答一律使用繁體中文。"},
        {"role": "user", "content": "我上週訂的貨到哪了?"},
        {"role": "assistant", "content": "請提供訂單編號,我幫您查詢。"},
        {"role": "user", "content": "訂單編號是 A12345"},
    ]
    answer = chat_messages("google/gemini-2.5-flash", history, temperature=0.3)
    print(answer)
    # 下一輪:把模型回覆 append 回 history 再呼叫,即可延續對話
    # history.append({"role": "assistant", "content": answer})`;

const RESPONSE_EXAMPLE = `{
  "success": true,
  "code": 200,
  "data": "模型回答的文字內容...",
  "detail": "success"
}`;

const ERROR_EXAMPLE = `{
  "success": false,
  "code": 403,
  "data": null,
  "detail": "model_forbidden"
}`;

interface ErrorRow {
  status: number;
  code: string;
  desc: string;
}

const ERRORS: ErrorRow[] = [
  { status: 400, code: "feature_not_supported", desc: "請求帶了不支援的欄位(目前 videos 暫不支援)" },
  { status: 400, code: "project_code_required", desc: "未帶 X-Project-Code header" },
  { status: 400, code: "project_invalid", desc: "X-Project-Code 對應專案不存在 / 已停用 / 不屬於 SDK Key 的部門" },
  { status: 401, code: "unauthorized", desc: "SDK Key 或 User Token 無效 / 已被撤銷 / 兩者不屬同一部門" },
  { status: 403, code: "model_forbidden", desc: "模型未在白名單,或已被 admin 停用" },
  { status: 404, code: "model_not_found", desc: "OpenRouter 找不到此模型" },
  { status: 429, code: "rate_limited", desc: "OpenRouter Key 短時間呼叫過於頻繁;建議指數退避重試" },
  // { status: 429, code: "internal_busy", desc: "本地模型排隊已超時(data.retry_after_seconds);依該秒數退避後重試" },
  { status: 502, code: "openrouter_unavailable", desc: "OpenRouter 服務暫時不可用,請確認 OpenRouter Key 是否有正確加入" },
  // { status: 502, code: "internal_unavailable", desc: "本地模型 server 暫時不可用,稍後再試" },
  // { status: 500, code: "provider_misconfigured", desc: "本地模型設定未完成,請聯絡管理員" },
  { status: 500, code: "操作失敗", desc: "後端異常,請聯絡管理員並提供時間點" },
];

// 範例區的 nav bar 分頁:基本對話 / Web 搜尋 / 檔案上傳
const EXAMPLE_TABS = [
  { value: "basic", label: "基本對話" },
  { value: "websearch", label: "Web 搜尋（即時匯率）" },
  { value: "file", label: "檔案上傳（PDF）" },
  { value: "messages", label: "多輪對話（messages）" },
] as const;

type ExampleTab = (typeof EXAMPLE_TABS)[number]["value"];

export default function UserGuidePage() {
  const [exampleTab, setExampleTab] = React.useState<ExampleTab>("basic");

  return (
    <>
      <PageTitle
        title="使用者使用說明"
        description="SDK 使用者透過 SDK Key + User Token + Project Code 呼叫代理端點的完整說明"
      />

      <div className="flex flex-col gap-8">
        <Section id="overview" title="概述">
          <p>
            本平台為 OpenRouter API 的<strong>代理層</strong>:統一管理金鑰、模型白名單與用量稽核。
            使用者<strong>不需要</strong>登入此網站,只需要拿到管理員發放的三組憑證,即可在自己的程式碼或工具裡呼叫代理端點。
          </p>
          <p className="text-muted-foreground">
            管理員(admin)透過本網站集中發放與管理憑證、模型白名單與部門金鑰;成員(user)只接觸下面提到的「SDK Key + User Token + Project Code」三因子組合。
          </p>
        </Section>

        <Section id="credentials" title="取得憑證(由管理員發放)">
          <p>呼叫代理端點需要三組憑證,皆由管理員在後台建立後給予使用者:</p>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-xl border border-border p-4">
              <div className="flex items-center gap-2 mb-2">
                <Badge>X-SDK-Key</Badge>
              </div>
              <p className="text-sm text-muted-foreground mb-1">部門層級 · 存取金鑰</p>
              <p className="text-sm">
                以部門為單位發放,代表「<strong>哪個部門的程式在呼叫</strong>」。
                由 admin 於後台「存取金鑰 / SDK Keys」建立,格式類似
                <code className="font-mono text-sm"> ordsk_xxxxxxxxxxxx_xxxx…</code>。
              </p>
            </div>
            <div className="rounded-xl border border-border p-4">
              <div className="flex items-center gap-2 mb-2">
                <Badge>X-User-Token</Badge>
              </div>
              <p className="text-sm text-muted-foreground mb-1">使用者層級 · 加密 payload</p>
              <p className="text-sm">
                以個別使用者為單位發放,代表「<strong>哪個人在呼叫</strong>」。
                由 admin 於「使用者管理」頁針對 role=user 的使用者產生,
                為加密字串、內含使用者識別與發行時間。
              </p>
            </div>
            <div className="rounded-xl border border-border p-4">
              <div className="flex items-center gap-2 mb-2">
                <Badge>X-Project-Code</Badge>
              </div>
              <p className="text-sm text-muted-foreground mb-1">專案層級 · 代碼</p>
              <p className="text-sm">
                以部門下的專案為單位發放,代表「<strong>這次呼叫歸到哪個專案算用量</strong>」。
                值為「專案管理」頁顯示的 <code className="font-mono text-sm">代碼</code>欄(系統自動產生的數字字串)。
                同把 SDK Key 可呼叫同部門任一專案。
              </p>
            </div>
          </div>
          <p className="text-destructive text-sm">
            ⚠ SDK Key 與 User Token <strong>只在建立時顯示一次</strong>。請妥善保管,遺失只能請管理員重新發放(同時舊憑證會被撤銷)。
          </p>
          <p className="text-sm text-muted-foreground">
            ⚠ <strong>三者必須屬於同一部門</strong>(SDK Key / User Token 綁部門;Project 屬部門),否則代理端會回 <code>401 unauthorized</code> 或 <code>400 project_invalid</code>。
          </p>
        </Section>

        <Section id="apply" title="申請使用 API Key">
          <p>
            若你尚未取得憑證,可於左側選單<strong>「API Key 申請表單」</strong>頁面送出申請。填妥下列<strong>全部必填</strong>欄位後送出,管理員將據此審核並發放憑證:
          </p>
          <ul className="list-disc pl-5 flex flex-col gap-1">
            <li><strong>部門名稱</strong>、<strong>部門代號</strong>(如 <code className="font-mono">T000</code>)</li>
            <li><strong>專案名稱</strong></li>
            <li>
              <strong>專案連結</strong>:須為 <strong>GitHub</strong> 或 <strong>Replit</strong> 連結(例 <code className="font-mono">https://github.com/...</code>)
            </li>
            <li><strong>專案負責人名稱</strong>、<strong>專案負責人信箱</strong></li>
          </ul>
          <p className="text-sm text-muted-foreground">
            送出後可在同一頁下方查看自己的申請歷程(狀態為「待審核」)。實際審核 / 發放由管理員處理。
          </p>
        </Section>

        <Section id="apply-status" title="申請後的狀態與領取憑證">
          <p>送出申請後,系統會依內容自動判斷,出現以下其中一種結果:</p>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4">
              <div className="flex items-center gap-2 mb-2">
                <Badge variant="secondary">系統自動開通</Badge>
              </div>
              <p className="text-sm">
                Agent 已完成欄位驗證並<strong>自動建立憑證</strong>。可在申請<strong>詳情 / 列表</strong>點「<strong>領取憑證</strong>」,一次性取得
                <strong> SDK Key</strong>、<strong>User Token</strong> 與<strong>專案代碼</strong>。
              </p>
              <p className="text-destructive text-sm mt-2">
                ⚠ 憑證<strong>僅顯示一次</strong>,請立即複製妥善保管;關閉後無法再次檢視,遺失需請管理員重新發放。
              </p>
              <p className="text-sm text-muted-foreground mt-2">
                📧 開通成功後,系統會自動以 <strong>Email</strong> 將憑證寄給<strong>專案負責人</strong>(申請時填的<strong>負責人信箱 <code className="font-mono">owner_email</code></strong>)。若負責人未收到,可請管理員於申請詳情<strong>重送通知</strong>,或由本人在此頁點「領取憑證」取得。
              </p>
            </div>
            <div className="rounded-xl border border-border p-4">
              <div className="flex items-center gap-2 mb-2">
                <Badge>待人工處理</Badge>
              </div>
              <p className="text-sm">
                由管理員<strong>審核</strong>後再發放。在管理員處理前,你可自行
                「<strong>取消</strong>」(需填取消原因)或「<strong>撤銷</strong>」這筆申請。
              </p>
            </div>
          </div>
          <ul className="list-disc pl-5 flex flex-col gap-1 text-sm text-muted-foreground">
            <li><strong>已取消</strong>:申請已停止處理(由你主動取消,附原因),不會再被發放。</li>
            <li><strong>已撤銷</strong>:申請已被收回作廢,不再進入審核 / 發放流程。</li>
            <li><strong>重複申請</strong>:若送出與既有申請重複的內容,系統會<strong>自動取消</strong>該筆,避免重複建立。</li>
          </ul>
        </Section>

        <Section id="endpoint" title="端點與認證 Header">
          <p>
            本平台提供<strong>測試</strong>與<strong>正式</strong>兩個環境,請依用途選用對應的 Base URL;以下範例皆以正式環境為準。
          </p>
          <div className="overflow-x-auto">
            <Table>
              <THead>
                <TR>
                  <TH>環境</TH>
                  <TH>Base URL</TH>
                </TR>
              </THead>
              <TBody>
                {API_ENVIRONMENTS.map((e) => (
                  <TR key={e.label}>
                    <TD>{e.label}</TD>
                    <TD className="font-mono text-sm">
                      {e.base || (
                        <span className="text-muted-foreground">(待補)</span>
                      )}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
          <p>所有呼叫皆透過下面這支端點:</p>
          <CodeBlock language="HTTP" code={`POST ${CHAT_URL}\nContent-Type: application/json\nX-SDK-Key: <SDK Key 明文>\nX-User-Token: <User Token 明文>\nX-Project-Code: <專案代碼>`} />
          <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
            <li>三個 Header <strong>皆必填</strong>;缺 SDK Key / User Token 回 <code>401 unauthorized</code>,缺 X-Project-Code 回 <code>400 project_code_required</code>,Project 不屬該部門 / 已停用 回 <code>400 project_invalid</code>。</li>
            <li>請勿把憑證寫死於前端 / 公開 repo / 客戶端 App;只能存放在受控的後端或 CI Secret 環境變數。</li>
          </ul>
        </Section>

        <Section id="request" title="Request Body">
          <p>JSON body 欄位如下:</p>
          <div className="overflow-x-auto">
            <Table>
              <THead>
                <TR>
                  <TH>欄位</TH>
                  <TH>型別</TH>
                  <TH>必填</TH>
                  <TH>說明</TH>
                </TR>
              </THead>
              <TBody>
                <TR>
                  <TD className="font-mono">model</TD>
                  <TD>string</TD>
                  <TD>是</TD>
                  <TD>OpenRouter 模型 id(例:<code>google/gemini-2.5-flash</code>),須在管理員設定的白名單內</TD>
                </TR>
                <TR>
                  <TD className="font-mono">text</TD>
                  <TD>string</TD>
                  <TD>否</TD>
                  <TD>使用者輸入的文字</TD>
                </TR>
                <TR>
                  <TD className="font-mono">images</TD>
                  <TD>string[]</TD>
                  <TD>否</TD>
                  <TD>圖片 URL 或 <code>data:image/...;base64,...</code> 字串陣列</TD>
                </TR>
                <TR>
                  <TD className="font-mono">files</TD>
                  <TD>object[]</TD>
                  <TD>否</TD>
                  <TD>上傳檔案(如 PDF),每筆為 <code>{`{ filename, file_data }`}</code>;<code>file_data</code> 為 <code>data:application/pdf;base64,...</code> 或可公開存取的遠端 URL。<strong>自 v2.2.1 起,用量紀錄除 <code>filename</code> 外亦留存檔案內容</strong>(存於公司自有 S3,見下方<strong>附件儲存與保存政策</strong>)</TD>
                </TR>
                <TR>
                  <TD className="font-mono">videos</TD>
                  <TD>string[]</TD>
                  <TD>否</TD>
                  <TD>暫不支援,送出即回 <code>400 feature_not_supported</code></TD>
                </TR>
                <TR>
                  <TD className="font-mono">tools</TD>
                  <TD>object[]</TD>
                  <TD>否</TD>
                  <TD>工具清單,格式同 OpenAI <code>tools</code> 規格,原樣轉發給下游。<strong>目前僅支援 OpenRouter server 端內建工具</strong>(如 web search,見下方範例);會回 <code>tool_calls</code> 的 function calling 尚未開放。<strong>單輪與 messages 兩種模式皆可搭配</strong></TD>
                </TR>
                <TR>
                  <TD className="font-mono">messages</TD>
                  <TD>object[]</TD>
                  <TD>否</TD>
                  <TD><strong>多輪對話模式</strong>:OpenAI 風格 <code>{`{ role, content }`}</code> 訊息陣列(system prompt / 對話歷史)。與 <code>text</code> / <code>images</code> / <code>files</code> <strong>擇一使用</strong>,同時帶回 <code>400</code>。詳見下方<strong>多輪對話(messages)與生成參數</strong></TD>
                </TR>
                <TR>
                  <TD className="font-mono">temperature</TD>
                  <TD>number</TD>
                  <TD>否</TD>
                  <TD>取樣隨機性,<code>0</code>–<code>2</code>;越低越穩定、越高越發散。未帶則用模型預設值</TD>
                </TR>
                <TR>
                  <TD className="font-mono">max_tokens</TD>
                  <TD>integer</TD>
                  <TD>否</TD>
                  <TD>回覆長度上限(token 數),<code>≥ 1</code>;未帶則用模型預設值</TD>
                </TR>
                <TR>
                  <TD className="font-mono">response_format</TD>
                  <TD>object</TD>
                  <TD>否</TD>
                  <TD>結構化輸出:<code>{`{"type":"json_object"}`}</code>(回覆保證為合法 JSON)或 <code>{`{"type":"json_schema","json_schema":{...}}`}</code>(指定 schema)。未帶則為一般文字回覆</TD>
                </TR>
              </TBody>
            </Table>
          </div>
          <p className="text-muted-foreground text-sm">
            可用的 <code>model</code> 清單由管理員集中維護。你可隨時查詢已啟用的模型清單(見下方<strong>查詢可用模型清單</strong>),從中複製 <code>model_key</code> 填入此欄位;若呼叫時收到 <code>403 model_forbidden</code>,請向管理員確認該模型是否已啟用。
          </p>

          <div className="mt-2 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4 flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <Badge variant="secondary">GET</Badge>
              <span className="font-medium text-sm">查詢可用模型清單</span>
            </div>
            <p className="text-sm text-muted-foreground">
              以 GET 取得目前<strong>已啟用</strong>的完整模型清單:
            </p>
            <CodeBlock language="HTTP" code={`GET ${MODELS_URL}`} />
            <ul className="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
              <li>
                此端點<strong>不需任何憑證</strong>,可直接於瀏覽器開啟:
                {" "}
                <a
                  href={MODELS_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="font-mono text-sm underline underline-offset-2 hover:text-foreground"
                >
                  {MODELS_URL}
                </a>
              </li>
              <li>
                回應 <code>data[]</code>(陣列)每筆的 <code>model_key</code> 即為呼叫上方端點時 <code>model</code> 欄位要填入的值;<code>name</code> 為顯示名稱、<code>description</code> / <code>context_length</code> / <code>modality</code> / <code>input_modalities</code> / <code>output_modalities</code> 供參考(modality tag 為陣列,例 [&quot;text&quot;,&quot;image&quot;])。
              </li>
              <li>僅回傳已啟用(白名單內)的模型;定價、tokenizer 等內部欄位不對外。</li>
            </ul>
          </div>

          <p className="font-medium mt-2">含圖片的 Request 範例:</p>
          <CodeBlock language="JSON" code={IMAGE_EXAMPLE} />

          <p className="font-medium mt-2">啟用 web search 的 Request 範例:</p>
          <CodeBlock language="JSON" code={TOOLS_EXAMPLE} />
          <ul className="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
            <li>帶 <code>tools</code> 即可啟用 OpenRouter <strong>server 端內建工具</strong>;web search 由 OpenRouter 在伺服器端執行搜尋後讓模型生成回覆,<strong>回應仍是純文字</strong>,呼叫與處理方式與一般請求完全相同。</li>
            <li><code>tools</code> 內容原樣轉發給 OpenRouter,平台不另行驗證;格式 / 可用工具型別以 OpenRouter 官方文件為準,傳錯會由 OpenRouter 回對應錯誤。</li>
            <li>啟用 web search 會由 OpenRouter 額外計費,費用一併反映在用量統計中。</li>
          </ul>

          <p className="font-medium mt-2">含檔案的 Request 範例(PDF):</p>
          <CodeBlock language="JSON" code={FILE_EXAMPLE} />
          <ul className="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
            <li>每筆檔案需給 <code>filename</code> 與 <code>file_data</code>;<code>file_data</code> 可填 base64 data URL 或可公開存取的遠端 URL。檔案解析由 OpenRouter 處理(模型原生支援則直接傳入,否則由 OpenRouter 解析後再送模型),可能產生額外計費。</li>
            <li><strong>保存政策(v2.2.1 起變更):用量紀錄除 <code>filename</code> 外亦留存檔案內容</strong>,存於公司自有 AWS S3(private,不對外公開),取用一律經後端簽發的短期連結;<strong>v2.2.1 之前的歷史紀錄只有檔名、沒有內容</strong>。詳見下方<strong>附件儲存與保存政策</strong>。</li>
          </ul>
          {/* 本地模型區塊暫時隱藏(待實際導入企業內部模型再開啟)
          <div className="mt-4 rounded-xl border border-purple-500/30 bg-purple-500/5 p-3 text-sm">
            <p className="font-medium text-purple-700 mb-1">本地模型(企業內部 server)</p>
            <p className="text-muted-foreground">
              呼叫方式<strong>完全相同</strong>(同 endpoint、同 header),只是 <code>model</code> 字串改成管理員給你的本地模型 id(慣例 <code>internal/&lt;name&gt;</code>)。本地模型可能因排隊或速率限制延後執行,若收到 <code>429 internal_busy</code> 並帶 <code>data.retry_after_seconds</code>,請依該秒數退避後重試。
            </p>
          </div>
          */}
        </Section>

        <Section id="messages" title="多輪對話(messages)與生成參數">
          <p>
            自 <strong>v2.1.2</strong> 起,除了單輪的 <code>text / images / files</code>,也可以直接帶 OpenAI 風格的 <code>messages</code> 陣列——
            自行組 <strong>system prompt、多輪對話歷史與角色設定</strong>,適合對話記憶、客服機器人等進階串接;
            並可搭配三個<strong>生成參數</strong>控制回覆行為。
          </p>

          <p className="font-medium">messages 使用規則</p>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>擇一使用</strong>:<code>messages</code> 與 <code>text</code> / <code>images</code> / <code>files</code> <strong>互斥</strong>,同時帶回 <code>400</code>;<code>messages: []</code>(空陣列)也回 <code>400</code>。</li>
            <li><strong>role 白名單</strong>:每則訊息的 <code>role</code> 只接受 <code>system</code> / <code>user</code> / <code>assistant</code>(<code>tool</code> 角色尚未開放)。</li>
            <li><strong>content 兩種寫法</strong>:純文字字串;或 parts 陣列——型別只接受 <code>text</code> / <code>image_url</code> / <code>file</code>(能力與單輪模式相同,影片同樣不支援)。</li>
            <li><strong>則數不設上限</strong>:以所選模型的 context window 為自然上限(全部訊息都計入 token),超過由模型端回錯誤。</li>
            <li><code>tools</code>(如 web search)兩種模式皆可搭配;回應格式<strong>不變</strong>,仍為統一格式的純文字 <code>data</code>。</li>
            <li>對話歷史由<strong>呼叫端自行保存與帶入</strong>,平台不儲存 session;messages 內容會寫入用量紀錄供稽核(其中的圖片與檔案自 v2.2.1 起改存公司自有 S3,見下方<strong>附件儲存與保存政策</strong>),請勿夾帶敏感個資。</li>
          </ul>

          <p className="font-medium mt-2">多輪對話 Request 範例:</p>
          <CodeBlock language="JSON" code={MESSAGES_EXAMPLE} />

          <p className="font-medium mt-2">生成參數(單輪與 messages 模式皆可帶)</p>
          <div className="overflow-x-auto">
            <Table>
              <THead>
                <TR>
                  <TH>參數</TH>
                  <TH>值域</TH>
                  <TH>用途</TH>
                </TR>
              </THead>
              <TBody>
                <TR>
                  <TD className="font-mono">temperature</TD>
                  <TD><code>0</code> – <code>2</code></TD>
                  <TD className="text-muted-foreground">控制隨機性:偏低(如 <code>0.2</code>)適合抽取 / 分類等要穩定的任務;偏高適合創意生成</TD>
                </TR>
                <TR>
                  <TD className="font-mono">max_tokens</TD>
                  <TD><code>≥ 1</code></TD>
                  <TD className="text-muted-foreground">限制回覆長度上限,控制成本與回覆篇幅</TD>
                </TR>
                <TR>
                  <TD className="font-mono">response_format</TD>
                  <TD><code>json_object</code> / <code>json_schema</code></TD>
                  <TD className="text-muted-foreground"><code>{`{"type":"json_object"}`}</code> 讓回覆保證為合法 JSON 字串(prompt 中請同時明確要求輸出 JSON);<code>{`{"type":"json_schema","json_schema":{...}}`}</code> 可進一步指定結構</TD>
                </TR>
              </TBody>
            </Table>
          </div>
          <CodeBlock language="JSON" code={GENPARAMS_EXAMPLE} />
          <ul className="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
            <li>三個參數<strong>未帶就不會送給模型</strong>,一律走模型預設值;超出值域(如 <code>temperature: 2.5</code>)回 <code>400</code>。</li>
            <li>其餘 OpenAI 生成參數(<code>top_p</code> / <code>stop</code> / <code>frequency_penalty</code> 等)<strong>不開放</strong>,帶了會被拒收,請勿嘗試。</li>
            <li>有帶的生成參數會一併寫入用量紀錄,方便事後追溯呼叫條件。</li>
          </ul>
        </Section>

        <Section id="response" title="Response 格式">
          <p>所有回應皆包在統一格式中:</p>
          <CodeBlock language="JSON (success)" code={RESPONSE_EXAMPLE} />
          <p>失敗回應:</p>
          <CodeBlock language="JSON (failure)" code={ERROR_EXAMPLE} />
          <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
            <li><code>success</code>:布林,程式判斷成功失敗。</li>
            <li><code>code</code>:對應 HTTP status。</li>
            <li><code>data</code>:成功時為<strong>模型回答的純文字字串</strong>(已剝除 id / usage / provider 等內部欄位)。</li>
            <li><code>detail</code>:成功固定為 <code>&quot;success&quot;</code>;失敗為錯誤碼或中文描述。</li>
          </ul>
        </Section>

        <Section id="examples" title="完整範例">
          {/* nav bar:切換基本對話 / Web 搜尋範例 */}
          <div className="flex gap-1 border-b border-border">
            {EXAMPLE_TABS.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setExampleTab(t.value)}
                className={cn(
                  "-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors hover:cursor-pointer",
                  exampleTab === t.value
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          {exampleTab === "basic" && (
            <>
              <p className="font-medium">curl</p>
              <CodeBlock language="bash" code={CURL_EXAMPLE} />
              <p className="font-medium">Python (httpx)</p>
              <CodeBlock language="python" code={PYTHON_EXAMPLE} />
            </>
          )}
          {exampleTab === "websearch" && (
            <>
              <p className="text-sm text-muted-foreground">
                帶 <code>tools: [{`{ "type": "openrouter:web_search" }`}]</code> 啟用
                OpenRouter server 端 web search;模型會即時查網路後回答(如查今日匯率),
                <strong>回應仍為純文字</strong>,呼叫方式與一般請求相同。web search 會由
                OpenRouter 額外計費。
              </p>
              <p className="font-medium">curl</p>
              <CodeBlock language="bash" code={CURL_WEBSEARCH_EXAMPLE} />
              <p className="font-medium">Python (httpx)</p>
              <CodeBlock language="python" code={PYTHON_WEBSEARCH_EXAMPLE} />
            </>
          )}
          {exampleTab === "file" && (
            <>
              <p className="text-sm text-muted-foreground">
                帶 <code>files</code> 即可附上 PDF 等檔案讓模型閱讀。<code>file_data</code> 可填
                可公開存取的遠端 URL(下方 curl 範例)或本機檔案轉成的 base64 data URL(下方 Python 範例)。
                <strong>自 v2.2.1 起,用量紀錄除檔名外亦留存檔案內容</strong>(存於公司自有 S3,private;見下方<strong>附件儲存與保存政策</strong>)。
              </p>
              <p className="font-medium">curl(遠端 URL,最容易測試)</p>
              <CodeBlock language="bash" code={CURL_FILE_EXAMPLE} />
              <p className="font-medium">Python (httpx,讀本機 PDF → base64)</p>
              <CodeBlock language="python" code={PYTHON_FILE_EXAMPLE} />
            </>
          )}
          {exampleTab === "messages" && (
            <>
              <p className="text-sm text-muted-foreground">
                帶 <code>messages</code> 陣列自組 system prompt 與對話歷史(與 <code>text/images/files</code> 擇一);
                此例同時示範 <code>temperature</code> 生成參數。詳細規則見上方
                <strong>多輪對話(messages)與生成參數</strong>。
              </p>
              <p className="font-medium">curl</p>
              <CodeBlock language="bash" code={CURL_MESSAGES_EXAMPLE} />
              <p className="font-medium">Python (httpx)</p>
              <CodeBlock language="python" code={PYTHON_MESSAGES_EXAMPLE} />
            </>
          )}
        </Section>

        <Section id="stream" title="串流回應(SSE)">
          <p>
            若希望像 ChatGPT 一樣<strong>逐字即時顯示</strong>回應(而非等整段生成完才一次回),
            可改用串流端點。回應以 <strong>SSE(Server-Sent Events)</strong> 一段一段傳回,每段只含 <code>id</code> 與該段文字 <code>content</code>。
          </p>
          <CodeBlock
            language="HTTP"
            code={`POST ${STREAM_URL}\nContent-Type: application/json\nX-SDK-Key: <SDK Key 明文>\nX-User-Token: <User Token 明文>\nX-Project-Code: <專案代碼>`}
          />
          <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
            <li>
              Header 與 Request Body <strong>與 <code>/model/chat</code> 完全相同</strong>(<code>model</code> / <code>text</code> / <code>images</code> / <code>files</code> / <code>tools</code>,v2.1.2 起亦含 <code>messages</code> 多輪與 <code>temperature</code> / <code>max_tokens</code> / <code>response_format</code> 生成參數);
              <strong>不需</strong>額外帶 <code>stream</code> 欄位,端點本身即代表串流。
            </li>
            <li>
              回應 <code>Content-Type</code> 為 <code>text/event-stream</code>,<strong>不</strong>套用統一
              {" "}<code>{`{ success, code, data, detail }`}</code> 包裝;每筆事件為精簡的
              {" "}<code>{`data: {"id":"...","content":"..."}`}</code>,最後以 <code>data: [DONE]</code> 收尾。
              文字內容位於 <code>content</code>;OpenRouter 的 <code>provider</code> / <code>cost</code> / <code>usage</code> 等內部欄位<strong>不會</strong>外露。
            </li>
            <li>
              <strong>開串流前</strong>的錯誤(憑證 / 白名單 / 速率限制等)仍以一般 HTTP 4xx/5xx +
              {" "}<code>{`{ success:false, … }`}</code> JSON 回絕,<strong>不</strong>會進入串流;
              程式應先檢查回應 <code>Content-Type</code> 再決定是否逐塊讀取。
            </li>
            <li>
              本端點<strong>僅支援 OpenRouter 模型</strong>;internal 模型呼叫此端點會回 <code>400 feature_not_supported</code>。
            </li>
          </ul>

          <p className="font-medium mt-2">curl(<code>-N</code> 關閉緩衝才看得到逐段輸出)</p>
          <CodeBlock language="bash" code={CURL_STREAM_EXAMPLE} />

          <p className="font-medium mt-2">curl(Windows PowerShell — 請用 <code>curl.exe</code>,勿用 <code>curl</code> 別名)</p>
          <CodeBlock language="powershell" code={CURL_STREAM_PWSH_EXAMPLE} />

          <p className="font-medium mt-2">預期輸出(成功時的 SSE 串流)</p>
          <CodeBlock language="text/event-stream" code={STREAM_OUTPUT_EXAMPLE} />
          <p className="text-sm text-muted-foreground">
            把每筆 <code>data:</code> 的 <code>content</code> 依序串接即為完整回答,遇 <code>data: [DONE]</code> 結束;
            <code>id</code> 為本次生成的識別碼(每段相同,可用於回報問題)。token 用量只記在後台,不隨串流回傳。
          </p>

          <p className="font-medium mt-2">Python (httpx 串流)</p>
          <CodeBlock language="python" code={PYTHON_STREAM_EXAMPLE} />

          <div className="mt-2 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4 flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <Badge variant="secondary">測試</Badge>
              <span className="font-medium text-sm">怎麼確認串流正常運作</span>
            </div>
            <ul className="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
              <li>
                <strong>串流成功</strong>:用上方 <code>curl -N</code> 應看到「逐段 <code>{`data: {"id":...,"content":...}`}</code> → 最後 <code>data: [DONE]</code>」逐字浮現;
                若整段一次才出現,多半是中間 proxy 緩衝。
              </li>
              <li>
                <strong>驗開串流前錯誤</strong>:故意把 <code>model</code> 填一個不在白名單的值,應回<strong>一般 JSON</strong>
                {" "}<code>{`{"success":false,"detail":"model_forbidden"}`}</code>(而非 SSE)。
              </li>
              <li>
                <strong>對照非串流</strong>:同參數打 <code>/model/chat</code> 應回 <code>{`{"success":true,"data":"…整段文字…"}`}</code>,可區分是串流問題還是基本鏈路問題。
              </li>
            </ul>
          </div>
        </Section>

        <Section id="errors" title="錯誤碼對照">
          <div className="overflow-x-auto">
            <Table>
              <THead>
                <TR>
                  <TH>HTTP</TH>
                  <TH>detail</TH>
                  <TH>說明 / 建議處理</TH>
                </TR>
              </THead>
              <TBody>
                {ERRORS.map((e) => (
                  <TR key={e.status + e.code}>
                    <TD>
                      <Badge variant={e.status >= 500 ? "destructive" : "secondary"}>
                        {e.status}
                      </Badge>
                    </TD>
                    <TD className="font-mono text-sm">{e.code}</TD>
                    <TD className="text-muted-foreground">{e.desc}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
        </Section>

        <Section id="attachments" title="附件儲存與保存政策(v2.2.1)">
          <p>
            自 <strong>v2.2.1</strong> 起,請求中夾帶的圖片與檔案改存<strong>公司自有 AWS S3</strong>,
            用量紀錄本身只留物件位置。本段說明這對你(呼叫端)與管理端各代表什麼。
          </p>

          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4 flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <Badge variant="secondary">呼叫端</Badge>
              <span className="font-medium text-sm">契約不變,零改動</span>
            </div>
            <ul className="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
              <li>
                <code>/model/chat</code>、<code>/model/chat/stream</code> 與 deprecated
                {" "}<code>/model/openrouter/chat</code> 的 <strong>request / response 格式完全不變</strong>;
                仍可<strong>照舊送 base64 data URI</strong>,<strong>不需要</strong>改任何程式碼。
              </li>
              <li>
                <strong>送給模型的內容也不變</strong>:平台轉送給下游模型的請求內容與 v2.2.0
                <strong>完全相同</strong>(圖片仍為原本的 base64 或原始 URL、<code>file_data</code> 照舊),已由回歸測試逐欄驗證;
                <strong>模型回應品質不受本版影響</strong>。
              </li>
              <li>本版改變的<strong>只有平台後端寫進用量紀錄的儲存形式</strong>。</li>
            </ul>
          </div>

          <p className="font-medium mt-2">存放位置與取用方式</p>
          <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
            <li>圖片 / 檔案存放於<strong>公司自有 AWS S3</strong>,物件一律 <strong>private、不對外公開</strong>(無公開網址)。</li>
            <li>檢視時(管理端用量明細頁)一律透過後端當場簽發的<strong>短期連結</strong>取得,<strong>預設有效期 15 分鐘</strong>;過期即失效,重新開啟頁面即可取得新連結。</li>
            <li>原本就送<strong>遠端 <code>https://</code> URL</strong> 的附件,平台<strong>原樣保留該 URL、不代抓</strong>,可讀性仍取決於該外部站台。</li>
          </ul>

          <p className="font-medium mt-2">檔案(PDF 等)自 v2.2.1 起才留存內容</p>
          <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
            <li>v2.2.1 之前,<code>files</code> 的用量紀錄<strong>只有檔名、沒有檔案內容</strong>。</li>
            <li><strong>自 v2.2.1 起才開始留存檔案內容</strong>,且<strong>只對新請求生效</strong>——本版之前的歷史紀錄<strong>不會、也無法</strong>補上內容。</li>
            <li>圖片內容則自始即有留存,本版只是換了存放位置。</li>
            <li>本項為平台端設定,由管理員啟用物件儲存後生效;未啟用時維持 v2.2.0 行為(圖片原樣快照、檔案僅記檔名)。</li>
          </ul>

          <p className="font-medium mt-2">管理端可見的行為變更</p>
          <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
            <li>
              用量明細 API 回吐的 <code>request_content</code> 中,<strong>圖片元素的語意由「base64 data URI 或遠端 URL」變更為「可直接顯示的短期 URL」</strong>;
              檔案元素則由「只有 <code>filename</code>」變成「<code>filename</code> + 可開啟的短期 URL」。
            </li>
            <li>此為<strong>管理端可見的行為變更</strong>;SDK 呼叫端的 request / response 不受影響。</li>
            <li>歷史紀錄在遷移完成前新舊形態並存,明細頁對兩種形態皆可正常顯示。</li>
          </ul>

          <p className="font-medium mt-2">S3 故障不影響代理可用性(best-effort)</p>
          <ul className="list-disc pl-5 space-y-1 text-muted-foreground">
            <li>附件上傳採 <strong>best-effort</strong>:S3 故障 / 逾時<strong>不會</strong>讓任何代理請求失敗——下游照常呼叫、回應照常返還、用量照常記帳。</li>
            <li>失敗時<strong>不會</strong>退回把 base64 寫進用量紀錄,而是在該筆紀錄標記「此附件未留存」並保留大小 / 型別等資訊,同時落 log 供追查。</li>
            <li>最壞情況只是<strong>該筆紀錄的附件內容沒留存</strong>,對外行為完全正常。</li>
          </ul>
        </Section>

        <Section id="security" title="安全注意事項">
          <ul className="list-disc pl-5 space-y-2">
            <li>
              <strong>不要</strong>把 SDK Key / User Token 寫死於前端(Browser / App)或 commit 到任何 git repo;只能存於後端服務、CI Secret、或加密的設定管理工具。
            </li>
            <li>
              若懷疑憑證外洩,<strong>立即</strong>聯絡管理員撤銷:User Token 撤銷後對應使用者所有舊 token 立即失效;SDK Key 撤銷後對應部門所有呼叫立即失效。
            </li>
            <li>所有呼叫都會記錄一筆 <code>usage_logs</code>(模型、token、耗時、是否成功);管理員可在後台<strong>用量紀錄</strong>頁面查詢。</li>
            <li>
              本平台<strong>不會</strong>儲存 OpenRouter 回傳的內部 metadata;但會保留請求內容(<code>text</code>、<code>images</code>、<code>messages</code>)以利稽核,請<strong>不要</strong>在 prompt 中夾帶敏感個資。
            </li>
            <li>
              <strong>附件保存(v2.2.1 起變更)</strong>:圖片與檔案(<code>files</code>)的內容存放於公司自有 AWS S3(private,不對外公開),用量紀錄本身只留物件位置;
              <code>file_data</code> 的 base64 內容<strong>任何情況下都不會寫入用量紀錄</strong>。政策全文見上方<strong>附件儲存與保存政策</strong>。
            </li>
          </ul>
        </Section>
      </div>
    </>
  );
}
