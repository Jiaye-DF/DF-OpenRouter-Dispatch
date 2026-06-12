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
                  <TD>上傳檔案(如 PDF),每筆為 <code>{`{ filename, file_data }`}</code>;<code>file_data</code> 為 <code>data:application/pdf;base64,...</code> 或可公開存取的遠端 URL。<strong>用量紀錄僅保留 <code>filename</code>,不留存檔案內容</strong></TD>
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
                  <TD>工具清單,格式同 OpenAI <code>tools</code> 規格,原樣轉發給下游。<strong>目前僅支援 OpenRouter server 端內建工具</strong>(如 web search,見下方範例);會回 <code>tool_calls</code> 的 function calling 尚未開放</TD>
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
            <li><strong>隱私:用量紀錄僅保留 <code>filename</code>,不留存檔案內容(<code>file_data</code>)</strong>;請避免在 <code>filename</code> 夾帶敏感資訊。</li>
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
                <strong>用量紀錄僅保留檔名,不留存檔案內容。</strong>
              </p>
              <p className="font-medium">curl(遠端 URL,最容易測試)</p>
              <CodeBlock language="bash" code={CURL_FILE_EXAMPLE} />
              <p className="font-medium">Python (httpx,讀本機 PDF → base64)</p>
              <CodeBlock language="python" code={PYTHON_FILE_EXAMPLE} />
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
              Header 與 Request Body <strong>與 <code>/model/chat</code> 完全相同</strong>(<code>model</code> / <code>text</code> / <code>images</code> / <code>files</code> / <code>tools</code>);
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
              本平台<strong>不會</strong>儲存 OpenRouter 回傳的內部 metadata;但會保留請求內容(<code>text</code>、含 base64 圖片)以利稽核,請<strong>不要</strong>在 prompt 中夾帶敏感個資。
            </li>
            <li>
              <strong>檔案上傳例外</strong>:<code>files</code> 僅保留 <code>filename</code>,<strong>不</strong>留存檔案內容(<code>file_data</code>);檔案內容僅於該次請求轉送 OpenRouter,不寫入用量紀錄。
            </li>
          </ul>
        </Section>
      </div>
    </>
  );
}
