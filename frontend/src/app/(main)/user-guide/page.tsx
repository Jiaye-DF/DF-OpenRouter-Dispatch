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
        <div className="px-4 py-1.5 text-xs text-muted-foreground border-b border-border font-mono">
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
          "absolute top-2 right-2 flex items-center gap-1 rounded-lg border border-border bg-background px-2 py-1 text-xs",
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

const IMAGE_EXAMPLE = `{
  "model": "google/gemini-2.5-flash",
  "text": "請描述這張圖片",
  "images": [
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...",
    "https://example.com/photo.jpg"
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

export default function UserGuidePage() {
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
              <p className="text-xs text-muted-foreground mb-1">部門層級 · 存取金鑰</p>
              <p className="text-sm">
                以部門為單位發放,代表「<strong>哪個部門的程式在呼叫</strong>」。
                由 admin 於後台「存取金鑰 / SDK Keys」建立,格式類似
                <code className="font-mono text-xs"> ordsk_xxxxxxxxxxxx_xxxx…</code>。
              </p>
            </div>
            <div className="rounded-xl border border-border p-4">
              <div className="flex items-center gap-2 mb-2">
                <Badge>X-User-Token</Badge>
              </div>
              <p className="text-xs text-muted-foreground mb-1">使用者層級 · 加密 payload</p>
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
              <p className="text-xs text-muted-foreground mb-1">專案層級 · 代碼</p>
              <p className="text-sm">
                以部門下的專案為單位發放,代表「<strong>這次呼叫歸到哪個專案算用量</strong>」。
                值為「專案管理」頁顯示的 <code className="font-mono text-xs">代碼</code>欄(系統自動產生的數字字串)。
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
                    <TD className="font-mono text-xs">
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
                  <TD className="font-mono">videos</TD>
                  <TD>string[]</TD>
                  <TD>否</TD>
                  <TD>暫不支援,送出即回 <code>400 feature_not_supported</code></TD>
                </TR>
              </TBody>
            </Table>
          </div>
          <p className="text-muted-foreground text-xs">
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
                  className="font-mono text-xs underline underline-offset-2 hover:text-foreground"
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
          <p className="font-medium">curl</p>
          <CodeBlock language="bash" code={CURL_EXAMPLE} />
          <p className="font-medium">Python (httpx)</p>
          <CodeBlock language="python" code={PYTHON_EXAMPLE} />
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
                    <TD className="font-mono text-xs">{e.code}</TD>
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
              本平台<strong>不會</strong>儲存 OpenRouter 回傳的內部 metadata;但會保留請求內容(含 base64 圖片)以利稽核,請<strong>不要</strong>在 prompt 中夾帶敏感個資。
            </li>
          </ul>
        </Section>
      </div>
    </>
  );
}
