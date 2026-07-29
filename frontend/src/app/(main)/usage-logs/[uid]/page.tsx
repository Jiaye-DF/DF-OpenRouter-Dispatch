"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Download, ExternalLink, RefreshCw } from "lucide-react";
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
  AttachmentFailureMeta,
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
//
// v2.2.1(task-528):附件落 S3 後,單一附件值同時存在**多種形態**(見 types/api.ts
// 「附件形態」段)。本頁一律先把原始值正規化成 ImageSource / FileEntry 再渲染,
// 所有判別都對 unknown 做 runtime 檢查——快照是歷史 JSONB,任何形狀都可能出現,
// 一列畸形不得讓整頁掛掉(propose §E)。

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

// ── 附件值正規化(v2.2.1)────────────────────────────────────────────────

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readString(source: unknown, key: string): string {
  if (!isRecord(source)) return "";
  const value = source[key];
  return typeof value === "string" ? value.trim() : "";
}

const DATA_URI_PREFIX = "data:";
const REMOTE_URL_RE = /^https?:\/\//i;
// presigned URL 必帶 SigV4(或舊式 SigV2)查詢參數;沒有就是呼叫端原本給的外部連結
// (後端 §D.2 對遠端 URL 原樣保留、不代抓)。此判別只影響標示文案,判錯不影響可用性。
const PRESIGNED_QUERY_RE = /[?&](X-Amz-Signature|X-Amz-Credential|AWSAccessKeyId)=/i;

type ContentLocation = "stored" | "external";

const LOCATION_LABELS: Record<ContentLocation, string> = {
  stored: "已存檔",
  external: "外部連結",
};

// 後端 attachment.py 的失敗原因短代碼;未列到的一律原樣顯示,不吞成空白。
const FAILURE_REASON_LABELS: Record<string, string> = {
  invalid_data_uri: "來源內容格式不正確",
  s3_upload_failed: "儲存服務上傳失敗",
  s3_unavailable: "儲存服務暫時無法使用",
};

function locationOf(url: string): ContentLocation {
  return PRESIGNED_QUERY_RE.test(url) ? "stored" : "external";
}

/** 取出上傳失敗標記的 metadata;非失敗標記 → null。image 走頂層、file 走 `file.*`。 */
function failureMetaOf(value: unknown): AttachmentFailureMeta | null {
  if (!isRecord(value)) return null;
  const inner = isRecord(value.file) ? value.file : null;
  const holder =
    value.upload_failed === true
      ? value
      : inner?.upload_failed === true
        ? inner
        : null;
  if (holder === null) return null;
  return {
    mime: typeof holder.mime === "string" ? holder.mime : undefined,
    bytes: typeof holder.bytes === "number" ? holder.bytes : undefined,
    sha256: typeof holder.sha256 === "string" ? holder.sha256 : undefined,
    reason: typeof holder.reason === "string" ? holder.reason : undefined,
  };
}

/** 取附件的內容參照:單輪 images 為字串本身,part 則取 `image_url.url` / `file.key`。 */
function refOf(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (!isRecord(value)) return "";
  return readString(value.image_url, "url") || readString(value.file, "key");
}

type ImageSource =
  | { kind: "url"; url: string; location: ContentLocation }
  | { kind: "data"; uri: string }
  | { kind: "failed"; meta: AttachmentFailureMeta }
  | { kind: "unavailable" };

function resolveImageSource(value: unknown): ImageSource {
  const meta = failureMetaOf(value);
  if (meta) return { kind: "failed", meta };

  const ref = refOf(value);
  if (!ref) return { kind: "unavailable" };
  if (ref.slice(0, DATA_URI_PREFIX.length).toLowerCase() === DATA_URI_PREFIX) {
    return { kind: "data", uri: ref };
  }
  if (REMOTE_URL_RE.test(ref)) {
    return { kind: "url", url: ref, location: locationOf(ref) };
  }
  // 既非 data URI 也非 http(s):presign 失敗時退回的 S3 物件路徑。
  // 直接塞進 <img src> 只會對本站發一個必然 404 的相對請求,故視為「連結未產生」。
  return { kind: "unavailable" };
}

type FileSource =
  | { kind: "link"; url: string; location: ContentLocation }
  | { kind: "failed"; meta: AttachmentFailureMeta }
  // v2.2.0(含全部歷史列)只留檔名,內容從未留存 → 不可點
  | { kind: "name-only" }
  // 有留存路徑但簽章連結沒產生出來(presign 失敗)→ 重新載入可能就好了
  | { kind: "unavailable" };

interface FileEntry {
  filename: string;
  source: FileSource;
}

function resolveFileEntry(value: unknown): FileEntry {
  if (typeof value === "string") {
    return { filename: value.trim(), source: { kind: "name-only" } };
  }
  const filename = readString(isRecord(value) ? value.file : undefined, "filename");
  const meta = failureMetaOf(value);
  if (meta) return { filename, source: { kind: "failed", meta } };

  const ref = refOf(value);
  if (!ref) return { filename, source: { kind: "name-only" } };
  if (REMOTE_URL_RE.test(ref)) {
    return { filename, source: { kind: "link", url: ref, location: locationOf(ref) } };
  }
  if (ref.slice(0, DATA_URI_PREFIX.length).toLowerCase() === DATA_URI_PREFIX) {
    // 快照理論上不留 file_data,但真出現時仍給得出可開啟的連結
    return { filename, source: { kind: "link", url: ref, location: "stored" } };
  }
  return { filename, source: { kind: "unavailable" } };
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${unit === 0 ? value : value.toFixed(1)} ${units[unit]}`;
}

// presigned URL 有 TTL(預設 15 分鐘),停留過久後圖片會載入失敗;
// 此 context 讓深層的附件元件能要求整筆明細重取,換一批新連結。
const ReloadContext = React.createContext<(() => void) | null>(null);

// ── 附件呈現元件 ────────────────────────────────────────────────────────

interface AttachmentMetaProps {
  meta: AttachmentFailureMeta;
}

function AttachmentMeta({ meta }: AttachmentMetaProps) {
  const items: string[] = [];
  if (meta.mime) items.push(`型別:${meta.mime}`);
  if (typeof meta.bytes === "number" && meta.bytes > 0) {
    items.push(`大小:${formatBytes(meta.bytes)}`);
  }
  if (meta.reason) {
    items.push(`原因:${FAILURE_REASON_LABELS[meta.reason] ?? meta.reason}`);
  }
  if (items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((text) => (
        <Badge key={text} variant="secondary" className="max-w-full break-all">
          {text}
        </Badge>
      ))}
    </div>
  );
}

interface AttachmentNoticeProps {
  title: string;
  description?: string;
  meta?: AttachmentFailureMeta;
  onReload?: () => void;
}

function AttachmentNotice({
  title,
  description,
  meta,
  onReload,
}: AttachmentNoticeProps) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border bg-muted/40 p-3">
      <span className="text-sm font-medium break-words">{title}</span>
      {description && (
        <span className="text-sm text-muted-foreground break-words">
          {description}
        </span>
      )}
      {meta && <AttachmentMeta meta={meta} />}
      {onReload && (
        <div>
          <Button variant="outline" size="sm" onClick={onReload}>
            <RefreshCw className="h-3.5 w-3.5" />
            重新載入
          </Button>
        </div>
      )}
    </div>
  );
}

interface ImageItemProps {
  // 單輪 `images[i]` 原始值(字串 / 失敗標記)或 messages 的 image_url part;
  // 形狀不保證(歷史 JSONB),一律經 resolveImageSource 正規化。
  value: unknown;
  index: number;
}

function ImageItem({ value, index }: ImageItemProps) {
  const source = React.useMemo(() => resolveImageSource(value), [value]);
  const reload = React.useContext(ReloadContext);
  const [blobUrl, setBlobUrl] = React.useState<string | null>(null);
  const [decodeFailed, setDecodeFailed] = React.useState(false);
  const [loadFailed, setLoadFailed] = React.useState(false);

  const dataUri = source.kind === "data" ? source.uri : null;

  React.useEffect(() => {
    if (dataUri === null) {
      setBlobUrl(null);
      setDecodeFailed(false);
      return;
    }
    const blob = dataUriToBlob(dataUri);
    if (!blob) {
      setBlobUrl(null);
      setDecodeFailed(true);
      return;
    }
    setDecodeFailed(false);
    const url = URL.createObjectURL(blob);
    setBlobUrl(url);
    // 元件卸載 / src 變更時釋放,避免 object URL 洩漏
    return () => URL.revokeObjectURL(url);
  }, [dataUri]);

  // 重新取明細後拿到新連結 → 清掉上一輪的載入失敗狀態
  React.useEffect(() => {
    setLoadFailed(false);
  }, [source]);

  const label = `圖片 #${index + 1}`;

  if (source.kind === "failed") {
    return (
      <AttachmentNotice
        title={`${label}:上傳失敗,內容未留存`}
        meta={source.meta}
      />
    );
  }

  if (source.kind === "unavailable") {
    return (
      <AttachmentNotice
        title={`${label}:內容連結未產生`}
        description="內容已留存,但這次沒能取得可讀取的連結。請重新載入再試。"
        onReload={reload ?? undefined}
      />
    );
  }

  if (decodeFailed) {
    return <AttachmentNotice title={`${label}:無法解析的內嵌內容`} />;
  }

  if (loadFailed) {
    return (
      <AttachmentNotice
        title={`${label}:圖片載入失敗`}
        description={
          source.kind === "data"
            ? "內嵌內容無法解碼為可顯示的圖片。"
            : "連結已逾時或失效(連結有效期約 15 分鐘)。請重新載入取得新連結。"
        }
        onReload={source.kind === "data" ? undefined : (reload ?? undefined)}
      />
    );
  }

  const displaySrc = source.kind === "data" ? blobUrl : source.url;
  const locationLabel =
    source.kind === "data" ? "已存檔・舊格式" : LOCATION_LABELS[source.location];

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-muted-foreground">
          {label}({locationLabel})
        </span>
        {displaySrc && (
          <div className="flex gap-3">
            <a
              href={displaySrc}
              target="_blank"
              rel="noreferrer"
              className="inline-flex min-h-[44px] items-center gap-1 text-sm underline underline-offset-2 hover:cursor-pointer hover:text-foreground md:min-h-0"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              開新分頁
            </a>
            <a
              href={displaySrc}
              download={`usage-image-${index + 1}`}
              className="inline-flex min-h-[44px] items-center gap-1 text-sm underline underline-offset-2 hover:cursor-pointer hover:text-foreground md:min-h-0"
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
          loading="lazy"
          onError={() => setLoadFailed(true)}
          className="max-h-80 w-auto max-w-full rounded-md border border-border object-contain"
        />
      ) : (
        <Skeleton className="h-40 w-full" />
      )}
    </div>
  );
}

interface FileItemProps {
  entry: FileEntry;
  index: number;
}

function FileItem({ entry, index }: FileItemProps) {
  const reload = React.useContext(ReloadContext);
  const name = entry.filename || "(未命名檔案)";
  const label = `檔案 #${index + 1}`;

  if (entry.source.kind === "failed") {
    return (
      <AttachmentNotice
        title={`${label}:${name} — 上傳失敗,內容未留存`}
        meta={entry.source.meta}
      />
    );
  }

  if (entry.source.kind === "unavailable") {
    return (
      <AttachmentNotice
        title={`${label}:${name}`}
        description="內容已留存,但這次沒能取得可讀取的連結。請重新載入再試。"
        onReload={reload ?? undefined}
      />
    );
  }

  if (entry.source.kind === "name-only") {
    return (
      <div className="flex flex-col gap-1 rounded-xl border border-border bg-muted/40 px-3 py-2">
        <span className="font-mono text-sm break-all">{name}</span>
        <span className="text-sm text-muted-foreground">
          (未留存)本版之前僅記錄檔名,未留存檔案內容
        </span>
      </div>
    );
  }

  const { url, location } = entry.source;
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border bg-muted/40 px-3 py-2">
      <span className="font-mono text-sm break-all">{name}</span>
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">
          ({LOCATION_LABELS[location]})
        </span>
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex min-h-[44px] items-center gap-1 text-sm underline underline-offset-2 hover:cursor-pointer hover:text-foreground md:min-h-0"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          開啟
        </a>
      </div>
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
// (text 文字 / image_url 沿用 ImageItem / file 沿用 FileItem)。
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
  let fileIndex = 0;
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
          return <ImageItem key={i} value={part} index={idx} />;
        }
        const idx = fileIndex;
        fileIndex += 1;
        return <FileItem key={i} entry={resolveFileEntry(part)} index={idx} />;
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
  // presigned URL 逾時後由附件元件觸發:重取整筆明細換一批新連結(v2.2.1)
  const [reloadTick, setReloadTick] = React.useState(0);
  const reload = React.useCallback(() => setReloadTick((n) => n + 1), []);

  React.useEffect(() => {
    if (!uid) return;
    setLoading(true);
    setError(null);
    apiClient
      .get<UsageLogDetail>(API_ENDPOINTS.usageLogById(uid))
      .then((data) => setLog(data))
      .catch((err) => {
        setError(
          err instanceof ApiError ? err.localizedDetail : "載入失敗"
        );
      })
      .finally(() => setLoading(false));
  }, [uid, reloadTick]);

  // request_content 雙內容模式(task-434):以 isMessagesRequest() 做形狀判別分流,
  // 舊單輪紀錄渲染路徑不變。
  const req: UsageRequestContent | null = log?.request_content ?? null;
  const resp = log?.response_summary ?? null;
  // v1.6.2 起 output_text 為完整回覆;舊紀錄僅有截斷的 first_text。
  const outputText = resp?.output_text ?? resp?.first_text ?? "";
  const isLegacyOutput = !resp?.output_text && !!resp?.first_text;

  return (
    <ReloadContext.Provider value={reload}>
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
                          {req.images.map((value, i) => (
                            <ImageItem key={i} value={value} index={i} />
                          ))}
                        </div>
                      </div>
                    )}

                    {req.files && req.files.length > 0 && (
                      <div className="flex flex-col gap-2">
                        <span className="text-sm text-muted-foreground">
                          上傳檔案({req.files.length})
                        </span>
                        <div className="flex flex-col gap-2">
                          {req.files.map((value, i) => (
                            <FileItem
                              key={i}
                              entry={resolveFileEntry(value)}
                              index={i}
                            />
                          ))}
                        </div>
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
    </ReloadContext.Provider>
  );
}
