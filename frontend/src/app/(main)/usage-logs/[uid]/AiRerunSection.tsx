"use client";

import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { formatUSD } from "@/lib/utils/format";
import {
  winnerLabel,
  winnerTone,
  formatConfidencePercent,
} from "@/lib/ai-eval-labels";
import type { RerunResult, RerunListResponse } from "@/types/api";

// v2.1.0(task-410):usage-log 明細頁「AI 分析卡」內嵌「AI 判決結果」摘要層
// + inline 展開的「真實重跑對比」詳細層(propose §6.1 / §6.2,決議 #6:落在現有卡內,
// 不依賴未建的 v2.0.4 專頁)。
//
// 獨立 fetch challenger 重跑結果(API_ENDPOINTS.aiRerunsByUsageLog),自有 loading /
// error / 狀態機;重跑缺漏不影響評審本體(AiAnalysisSection 各自 fetch)。
// 型別 / 端點 / label 一律取自 task-409 產物,禁重複定義或硬編端點字串。

// winnerTone → Badge variant(維持原模型=中性 / 建議改用=綠 / 平手=黃 / 未知=中性)。
// 集中映射,色調語意由 ai-eval-labels.winnerTone 決定(對齊 FIT_BAR_CLASS 集中慣例)。
const WINNER_BADGE_VARIANT: Record<
  ReturnType<typeof winnerTone>,
  React.ComponentProps<typeof Badge>["variant"]
> = {
  original: "secondary",
  challenger: "success",
  tie: "warning",
  none: "secondary",
};

// 成本Δ 文字色階:< 0(challenger 更省)=綠;> 0(更貴)=紅;= 0 / 無資料=中性。
// 沿用 AiAnalysisSection FIT_BAR_CLASS 的 emerald / destructive 色階慣例(對齊 task 要點)。
function costDeltaTone(delta: string | null): "save" | "cost" | "flat" {
  if (delta === null) return "flat";
  const n = Number(delta);
  if (!Number.isFinite(n) || n === 0) return "flat";
  return n < 0 ? "save" : "cost";
}

const COST_DELTA_CLASS: Record<ReturnType<typeof costDeltaTone>, string> = {
  save: "text-emerald-600",
  cost: "text-destructive",
  flat: "text-muted-foreground",
};

// 成本Δ 顯示字串:帶正負號(更貴 +、更省 −,與顏色語意一致),null → em dash。
function formatCostDelta(delta: string | null): string {
  if (delta === null) return "—";
  const n = Number(delta);
  if (!Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : ""; // 負值 toFixed 自帶 -,正值補 +
  return `${sign}${formatUSD(delta)}`;
}

// ISO → 顯示字串(對齊 04-datetime.md:DB 存 UTC+8 wall-clock,禁 toLocaleString /
// timeZone,以正規表示式切字串)。utils/datetime.ts 尚未建立(超出本 task 範圍),
// 暫於本檔比照 04-datetime.md 實作,已記入 fixed.md 待後續抽 util。
function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})/);
  return m ? `${m[1]}/${m[2]}/${m[3]} ${m[4]}:${m[5]}:${m[6]}` : iso;
}

// 單筆 challenger 的狀態:重跑失敗 / 已重跑·未裁決(子開關關,compare_* NULL)/ 已重跑。
type RerunRowState = "failed" | "judged" | "unjudged";

function rerunRowState(r: RerunResult): RerunRowState {
  if (r.status !== "success") return "failed";
  return r.compare_winner === null ? "unjudged" : "judged";
}

// 摘要層每列:原始 → challenger + 裁決 Badge + 信心分數(緊湊)。
function SummaryRow({ rerun }: { rerun: RerunResult }) {
  const state = rerunRowState(rerun);
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
      <span className="font-mono font-medium">{rerun.rerun_model}</span>
      {state === "failed" ? (
        <Badge variant="destructive">重跑失敗</Badge>
      ) : state === "unjudged" ? (
        <Badge variant="secondary">已重跑·未裁決</Badge>
      ) : (
        <>
          <Badge variant={WINNER_BADGE_VARIANT[winnerTone(rerun.compare_winner!)]}>
            {winnerLabel(rerun.compare_winner!)}
          </Badge>
          <span className="text-muted-foreground">
            信心 {formatConfidencePercent(rerun.compare_score)}
          </span>
        </>
      )}
    </div>
  );
}

// 詳細層每列:模型 + tier、真實成本與成本Δ、延遲、裁決 + 信心 + 理由、challenger 輸出。
// (challenger 輸出原文不在 RerunResult schema 內,本版顯示量化欄位 + 裁決理由。)
function DetailRow({ rerun }: { rerun: RerunResult }) {
  const state = rerunRowState(rerun);
  const deltaTone = costDeltaTone(rerun.cost_delta_usd);
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-muted/30 p-3">
      {/* 模型 + 狀態 Badge */}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="font-mono text-sm font-medium">
          {rerun.rerun_model}
        </span>
        {state === "failed" && <Badge variant="destructive">重跑失敗</Badge>}
        {state === "unjudged" && (
          <Badge variant="secondary">已重跑·未裁決</Badge>
        )}
        {state === "judged" && (
          <Badge variant={WINNER_BADGE_VARIANT[winnerTone(rerun.compare_winner!)]}>
            {winnerLabel(rerun.compare_winner!)}
          </Badge>
        )}
      </div>

      {state === "failed" ? (
        <span className="text-sm text-destructive">
          重跑失敗{rerun.error_code ? `(${rerun.error_code})` : ""},本列無對比資料。
        </span>
      ) : (
        <>
          {/* 量化欄位:成本 / 成本Δ / 延遲 / 執行時間 */}
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm md:grid-cols-4">
            <div className="flex flex-col">
              <dt className="text-muted-foreground">真實成本</dt>
              <dd className="font-mono">{formatUSD(rerun.cost_usd)}</dd>
            </div>
            <div className="flex flex-col">
              <dt className="text-muted-foreground">成本Δ(vs 原)</dt>
              <dd className={`font-mono ${COST_DELTA_CLASS[deltaTone]}`}>
                {formatCostDelta(rerun.cost_delta_usd)}
              </dd>
            </div>
            <div className="flex flex-col">
              <dt className="text-muted-foreground">延遲</dt>
              <dd className="font-mono">
                {rerun.latency_ms === null ? "—" : `${rerun.latency_ms} ms`}
              </dd>
            </div>
            <div className="flex flex-col">
              <dt className="text-muted-foreground">執行時間</dt>
              <dd>{formatDateTime(rerun.triggered_at)}</dd>
            </div>
          </dl>

          {/* 裁決:Badge(上方已顯示)+ 信心 + 理由;未裁決時提示 */}
          {state === "unjudged" ? (
            <span className="text-sm text-muted-foreground">
              對比裁決子開關關閉,本列僅有真實重跑用量、無裁決結果。
            </span>
          ) : (
            <div className="flex flex-col gap-1">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
                <span className="text-muted-foreground">信心分數</span>
                <span className="font-medium">
                  {formatConfidencePercent(rerun.compare_score)}
                </span>
                {rerun.compare_judge_model && (
                  <span className="text-muted-foreground">
                    · 裁決模型 {rerun.compare_judge_model}
                  </span>
                )}
              </div>
              {rerun.compare_reason && (
                <p className="text-sm text-muted-foreground">
                  {rerun.compare_reason}
                </p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function AiRerunSection({ uid }: { uid: string }) {
  const [reruns, setReruns] = React.useState<RerunResult[] | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [expanded, setExpanded] = React.useState(false);

  React.useEffect(() => {
    if (!uid) return;
    let alive = true;
    setLoading(true);
    setError(null);
    apiClient
      .get<RerunListResponse>(API_ENDPOINTS.aiRerunsByUsageLog(uid))
      .then((data) => {
        if (alive) setReruns(data.reruns);
      })
      .catch((err) => {
        if (alive) {
          setError(
            err instanceof ApiError ? err.localizedDetail : "載入重跑對比失敗"
          );
        }
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [uid]);

  // 彙總結論:在已裁決列中數「維持原模型」票(propose §6.1 例「2/3 建議維持」)。
  const verdictSummary = React.useMemo(() => {
    if (!reruns) return null;
    const judged = reruns.filter((r) => rerunRowState(r) === "judged");
    if (judged.length === 0) return null;
    const keep = judged.filter((r) => r.compare_winner === "original").length;
    const swap = judged.filter((r) => r.compare_winner === "challenger").length;
    if (keep > swap) return `${keep}/${judged.length} 建議維持原模型`;
    if (swap > keep) return `${swap}/${judged.length} 建議改用 challenger`;
    return `${judged.length} 筆裁決平分(無多數共識)`;
  }, [reruns]);

  return (
    <div className="flex flex-col gap-3 border-t border-border pt-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-muted-foreground">AI 判決結果</span>
        {reruns !== null && reruns.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="min-h-[44px] md:min-h-0"
            aria-expanded={expanded}
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? "收合對比" : "展開對比"}
          </Button>
        )}
      </div>

      {loading ? (
        // loading:Skeleton(對齊 AiAnalysisSection)
        <div className="flex flex-col gap-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </div>
      ) : error ? (
        // fetch error:顯示錯誤但不阻斷評審本體
        <span className="text-sm text-destructive">{error}</span>
      ) : reruns === null || reruns.length === 0 ? (
        // 狀態:未重跑(408 reruns:[] / 無重跑)
        <div className="rounded-lg bg-muted/50 p-4 text-sm text-muted-foreground">
          此筆尚無 challenger 重跑對比。
        </div>
      ) : (
        <>
          {/* 摘要層:緊湊逐 challenger 列 + 彙總結論 */}
          <div className="flex flex-col gap-2">
            {reruns.map((r) => (
              <SummaryRow key={`${r.rerun_model}-${r.triggered_at}`} rerun={r} />
            ))}
          </div>
          {verdictSummary && (
            <div>
              <Badge variant="secondary">{verdictSummary}</Badge>
            </div>
          )}

          {/* 詳細層:inline 展開(同卡內) */}
          {expanded && (
            <div className="flex flex-col gap-3">
              {reruns.map((r) => (
                <DetailRow
                  key={`${r.rerun_model}-${r.triggered_at}`}
                  rerun={r}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
