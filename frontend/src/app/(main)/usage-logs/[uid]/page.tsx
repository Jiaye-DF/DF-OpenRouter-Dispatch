"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Download, ExternalLink } from "lucide-react";
import { PageTitle } from "@/components/common/PageTitle";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AiAnalysisSection } from "./AiAnalysisSection";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { formatDateTime } from "@/lib/utils/datetime";
import { formatUSD } from "@/lib/utils/format";
import { useAppSelector } from "@/store/hooks";
import { isMessagesRequest } from "@/types/api";
import type {
  RequestGenerationParams,
  RequestMessage,
  RequestMessagePart,
  UsageLogDetail,
  UsageRequestContent,
} from "@/types/api";

// 用量紀錄單筆詳情頁:顯示使用者實際傳入內容(Input,含圖片)與模型完整回覆(Output)。
// base64 圖片在前端轉成 Blob/object URL 後渲染,避免巨大 data URI 直接塞進 DOM。
// v2.1.2(task-434):request_content 支援雙內容模式——舊單輪 {text, images, ...}
// 渲染不變;messages 直傳模式依 role 分段渲染(形狀判別,不做資料遷移)。
// 快照型別與 isMessagesRequest() 一律取自 types/api.ts(共用契約,不在本頁重複定義)。

function dataUriToBlob(dataUri: string): Blob | null {
  const m = /^data:([^;]+);base64,(.*)$/s.exec(dataUri);
  if (!m) return null;
  try {
    const bin = atob(m[2]);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new Blob([bytes], { type: m[1] });
  } catch {
    return null;
  }
}

function ImageItem({ src, index }: { src: string; index: number }) {
  const isDataUri = src.startsWith("data:");
  const [blobUrl, setBlobUrl] = React.useState<string | null>(null);
  const [failed, setFailed] = React.useState(false);

  React.useEffect(() => {
    if (!isDataUri) return;
    const blob = dataUriToBlob(src);
    if (!blob) {
      setFailed(true);
      return;
    }
    const url = URL.createObjectURL(blob);
    setBlobUrl(url);
    // 元件卸載 / src 變更時釋放,避免 object URL 洩漏
    return () => URL.revokeObjectURL(url);
  }, [src, isDataUri]);

  const displaySrc = isDataUri ? blobUrl : src;

  if (failed) {
    return (
      <div className="rounded-lg border border-border p-3 text-sm text-muted-foreground">
        圖片 #{index + 1}:無法解析的 base64 內容
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          圖片 #{index + 1}
          {isDataUri ? "(base64)" : "(URL)"}
        </span>
        {displaySrc && (
          <div className="flex gap-2">
            <a
              href={displaySrc}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-sm underline underline-offset-2 hover:text-foreground"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              開新分頁
            </a>
            <a
              href={displaySrc}
              download={`usage-image-${index + 1}`}
              className="inline-flex items-center gap-1 text-sm underline underline-offset-2 hover:text-foreground"
            >
              <Download className="h-3.5 w-3.5" />
              下載
            </a>
          </div>
        )}
      </div>
      {displaySrc ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={displaySrc}
          alt={`輸入圖片 ${index + 1}`}
          className="max-h-80 w-auto rounded-md border border-border object-contain"
        />
      ) : (
        <Skeleton className="h-40 w-full" />
      )}
    </div>
  );
}

// role → 視覺區辨(Badge 變體 + 中文說明);目前後端 role 走 Literal 白名單,僅此三種。
// 但 schema 已預告未來會開放 tool role,屆時舊紀錄仍會被本頁讀到:查無對應一律走
// ROLE_FALLBACK(以 role 原字串顯示),不可讓明細頁因未知 role 整頁崩掉。
type RoleMeta = { label: string; variant: "warning" | "default" | "success" | "secondary" };

const ROLE_META: Record<string, RoleMeta> = {
  system: { label: "系統提示", variant: "warning" },
  user: { label: "使用者", variant: "default" },
  assistant: { label: "助理", variant: "success" },
};

function roleMetaOf(role: string): RoleMeta {
  return ROLE_META[role] ?? { label: role, variant: "secondary" };
}

// 單則 message 的 content:字串直接顯示;parts 陣列依型別呈現
// (text 文字 / image_url 縮圖沿用 ImageItem / file 檔名)。
function MessageContent({
  content,
}: {
  content: string | RequestMessagePart[];
}) {
  if (typeof content === "string") {
    return content ? (
      <pre className="whitespace-pre-wrap break-words rounded-lg border border-border bg-muted/40 p-3 text-sm">
        {content}
      </pre>
    ) : (
      <span className="text-sm text-muted-foreground">(無內容)</span>
    );
  }

  let imageIndex = 0;
  return (
    <div className="flex flex-col gap-2">
      {content.map((part, i) => {
        if (part.type === "text") {
          return (
            <pre
              key={i}
              className="whitespace-pre-wrap break-words rounded-lg border border-border bg-muted/40 p-3 text-sm"
            >
              {part.text}
            </pre>
          );
        }
        if (part.type === "image_url") {
          const idx = imageIndex;
          imageIndex += 1;
          return <ImageItem key={i} src={part.image_url.url} index={idx} />;
        }
        return (
          <div
            key={i}
            className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm"
          >
            <span className="text-muted-foreground">檔案(僅保留檔名):</span>{" "}
            <span className="font-mono break-all">{part.file.filename}</span>
          </div>
        );
      })}
    </div>
  );
}

// messages 模式:單則訊息區塊(role Badge 標頭 + content)
function MessageBlock({ message }: { message: RequestMessage }) {
  const meta = roleMetaOf(message.role);
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
      <div className="flex items-center gap-2">
        <Badge variant={meta.variant} className="font-mono">
          {message.role}
        </Badge>
        <span className="text-sm text-muted-foreground">{meta.label}</span>
      </div>
      <MessageContent content={message.content} />
    </div>
  );
}

// tools 快照(兩種內容模式共用同一呈現)
function ToolsView({ tools }: { tools: Record<string, unknown>[] }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm text-muted-foreground">工具(tools)</span>
      <pre className="overflow-x-auto rounded-lg border border-border bg-muted/40 p-3 font-mono text-sm">
        {JSON.stringify(tools, null, 2)}
      </pre>
    </div>
  );
}

// 生成參數(v2.1.2):有帶才顯示;舊紀錄無這些鍵 → 不渲染(視覺不變)
function GenerationParamsView({ req }: { req: RequestGenerationParams }) {
  const hasAny =
    req.temperature !== undefined ||
    req.max_tokens !== undefined ||
    req.response_format !== undefined;
  if (!hasAny) return null;
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm text-muted-foreground">生成參數</span>
      <div className="flex flex-wrap gap-2">
        {req.temperature !== undefined && (
          <Badge variant="secondary" className="font-mono">
            temperature: {req.temperature}
          </Badge>
        )}
        {req.max_tokens !== undefined && (
          <Badge variant="secondary" className="font-mono">
            max_tokens: {req.max_tokens.toLocaleString()}
          </Badge>
        )}
        {req.response_format && (
          <Badge variant="secondary" className="font-mono">
            response_format: {req.response_format.type}
          </Badge>
        )}
      </div>
      {req.response_format?.type === "json_schema" &&
        req.response_format.json_schema && (
          <pre className="overflow-x-auto rounded-lg border border-border bg-muted/40 p-3 font-mono text-sm">
            {JSON.stringify(req.response_format.json_schema, null, 2)}
          </pre>
        )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export default function UsageLogDetailPage() {
  const router = useRouter();
  const params = useParams();
  const uid = Array.isArray(params.uid) ? params.uid[0] : params.uid;
  const role = useAppSelector((s) => s.auth.actor?.role);

  const [log, setLog] = React.useState<UsageLogDetail | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!uid) return;
    setLoading(true);
    apiClient
      .get<UsageLogDetail>(API_ENDPOINTS.usageLogById(uid))
      .then((data) => setLog(data))
      .catch((err) => {
        setError(
          err instanceof ApiError ? err.localizedDetail : "載入失敗"
        );
      })
      .finally(() => setLoading(false));
  }, [uid]);

  // request_content 雙內容模式(task-434):以 isMessagesRequest() 做形狀判別分流,
  // 舊單輪紀錄渲染路徑不變。
  const req: UsageRequestContent | null = log?.request_content ?? null;
  const resp = log?.response_summary ?? null;
  // v1.6.2 起 output_text 為完整回覆;舊紀錄僅有截斷的 first_text。
  const outputText = resp?.output_text ?? resp?.first_text ?? "";
  const isLegacyOutput = !resp?.output_text && !!resp?.first_text;

  return (
    <>
      <div className="mb-4">
        <Button
          variant="outline"
          size="sm"
          onClick={() => router.push("/usage-logs")}
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          返回用量紀錄
        </Button>
      </div>

      <PageTitle
        title="用量紀錄詳情"
        description="此筆呼叫的實際輸入(Input)與模型回覆(Output)"
      />

      {loading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : error ? (
        <Card>
          <CardContent className="pt-6 text-sm text-destructive">
            {error}
          </CardContent>
        </Card>
      ) : log ? (
        <div className="flex flex-col gap-6">
          {/* Metadata */}
          <Card>
            <CardContent className="grid grid-cols-2 gap-4 pt-6 md:grid-cols-4">
              <Field label="編號" value={<span className="font-mono">#{log.pid}</span>} />
              <Field
                label="時間"
                value={formatDateTime(log.created_at)}
              />
              <Field
                label="專案"
                value={
                  log.project_code ? (
                    <span>
                      <span className="font-mono">{log.project_code}</span>
                      {log.project_name ? ` · ${log.project_name}` : ""}
                    </span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )
                }
              />
              <Field label="模型" value={<span className="font-mono">{log.model}</span>} />
              <Field
                label="狀態"
                value={
                  <Badge
                    variant={log.status === "success" ? "success" : "destructive"}
                  >
                    {log.status === "success" ? "成功" : "失敗"}
                  </Badge>
                }
              />
              <Field
                label="工具"
                value={
                  log.used_tools ? (
                    <Badge variant="secondary">有用工具</Badge>
                  ) : (
                    <span className="text-muted-foreground">未用</span>
                  )
                }
              />
              <Field
                label="輸入 / 回覆 / 合計 Token"
                value={`${log.prompt_tokens.toLocaleString()} / ${log.completion_tokens.toLocaleString()} / ${log.total_tokens.toLocaleString()}`}
              />
              <Field label="花費 (USD)" value={formatUSD(log.cost_usd)} />
              <Field label="延遲" value={`${log.latency_ms} ms`} />
              {log.error_code && (
                <Field
                  label="錯誤碼"
                  value={<span className="text-destructive">{log.error_code}</span>}
                />
              )}
            </CardContent>
          </Card>

          {/* AI 分析(v2.0.3,task-306):掛在 metadata Card 下方,獨立 fetch 評審結果。
              v2.1.1:維持 admin-only,非-admin 檢視不渲染。 */}
          {uid && role === "admin" && <AiAnalysisSection uid={uid} />}

          {/* Input */}
          <section>
            <h2 className="mb-3 text-lg font-semibold">Input(使用者傳入)</h2>
            <Card>
              <CardContent className="flex flex-col gap-4 pt-6">
                {req ? (
                  isMessagesRequest(req) ? (
                    // messages 直傳模式(v2.1.2):依 role 分段渲染多輪內容
                    <>
                      <div className="flex flex-col gap-2">
                        <span className="text-sm text-muted-foreground">
                          多輪對話(messages,共 {req.messages.length} 則)
                        </span>
                        <div className="flex flex-col gap-3">
                          {req.messages.map((msg, i) => (
                            <MessageBlock key={i} message={msg} />
                          ))}
                        </div>
                      </div>

                      {req.tools && req.tools.length > 0 && (
                        <ToolsView tools={req.tools} />
                      )}

                      <GenerationParamsView req={req} />
                    </>
                  ) : (
                  <>
                    <div className="flex flex-col gap-1">
                      <span className="text-sm text-muted-foreground">文字</span>
                      {req.text ? (
                        <pre className="whitespace-pre-wrap break-words rounded-lg border border-border bg-muted/40 p-3 text-sm">
                          {req.text}
                        </pre>
                      ) : (
                        <span className="text-sm text-muted-foreground">(無)</span>
                      )}
                    </div>

                    {req.tools && req.tools.length > 0 && (
                      <ToolsView tools={req.tools} />
                    )}

                    {req.images && req.images.length > 0 && (
                      <div className="flex flex-col gap-2">
                        <span className="text-sm text-muted-foreground">
                          圖片({req.images.length})
                        </span>
                        <div className="flex flex-col gap-3">
                          {req.images.map((src, i) => (
                            <ImageItem key={i} src={src} index={i} />
                          ))}
                        </div>
                      </div>
                    )}

                    {req.files && req.files.length > 0 && (
                      <div className="flex flex-col gap-2">
                        <span className="text-sm text-muted-foreground">
                          上傳檔案({req.files.length}) — 僅保留檔名,不留存檔案內容
                        </span>
                        <ul className="flex flex-col gap-1">
                          {req.files.map((name, i) => (
                            <li
                              key={i}
                              className="rounded-lg border border-border bg-muted/40 px-3 py-2 font-mono text-sm break-all"
                            >
                              {name}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    <GenerationParamsView req={req} />
                  </>
                  )
                ) : (
                  <span className="text-sm text-muted-foreground">
                    此紀錄無請求內容(可能為歷史紀錄或白名單拒絕情境)
                  </span>
                )}
              </CardContent>
            </Card>
          </section>

          {/* Output */}
          <section>
            <h2 className="mb-3 text-lg font-semibold">Output(模型回覆)</h2>
            <Card>
              <CardContent className="flex flex-col gap-2 pt-6">
                {isLegacyOutput && (
                  <span className="text-sm text-amber-600">
                    ⚠ 舊紀錄:僅保留前 500 字摘要(完整回覆自 v1.6.2 起才記錄)
                  </span>
                )}
                {outputText ? (
                  <pre className="whitespace-pre-wrap break-words rounded-lg border border-border bg-muted/40 p-3 text-sm">
                    {outputText}
                  </pre>
                ) : (
                  <span className="text-sm text-muted-foreground">(無回覆內容)</span>
                )}
              </CardContent>
            </Card>
          </section>
        </div>
      ) : (
        <Card>
          <CardContent className="pt-6 text-sm text-muted-foreground">
            查無此紀錄
          </CardContent>
        </Card>
      )}
    </>
  );
}
