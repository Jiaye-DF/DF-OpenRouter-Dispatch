"use client";

import * as React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import {
  intentLabel,
  complexityLabel,
  formatFitPercent,
  fitTone,
} from "@/lib/ai-eval-labels";
import type {
  EvaluationResult,
  EvaluationResultResponse,
  EvaluationSummary,
} from "@/types/api";

// v2.0.3(task-306):usage-log 明細頁內嵌「AI 分析」基礎摘要區塊。
// 獨立 fetch 評審結果(評審缺漏不影響 log 本體),自有 loading / error / 四狀態機。
// 只渲染「基礎摘要卡」(propose §6.1);三評審逐筆明細留 v2.0.4(API 回 candidates 但本版不渲染)。

// fitTone → 進度條色階 class(高綠中黃低紅;none 灰)。集中映射,門檻由 ai-eval-labels.fitTone 決定。
const FIT_BAR_CLASS: Record<ReturnType<typeof fitTone>, string> = {
  high: "bg-emerald-500",
  mid: "bg-amber-500",
  low: "bg-destructive",
  none: "bg-muted-foreground/40",
};

// 平均吻合度進度條:寬度用百分比、顏色用 fitTone 色階;null 安全(寬 0 + 灰)。
function MetricBar({ score }: { score: string | null }) {
  const tone = fitTone(score);
  // 寬度直接取 score(0–1)轉百分比;解析失敗 / null → 0
  const n = score === null ? NaN : Number(score);
  const widthPct = Number.isFinite(n) ? Math.max(0, Math.min(100, n * 100)) : 0;
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
      <div
        className={`h-full rounded-full transition-all ${FIT_BAR_CLASS[tone]}`}
        style={{ width: `${widthPct}%` }}
      />
    </div>
  );
}

// 區塊小標(對齊 page.tsx 既有 muted 標籤風格)
function SectionLabel({ children }: { children: React.ReactNode }) {
  return <span className="text-sm text-muted-foreground">{children}</span>;
}

// 已評審 → 基礎摘要卡內容(propose §6.1)。summary / task_analysis 皆可能為 null,逐區防呆。
function EvaluatedSummary({ evaluation }: { evaluation: EvaluationResult }) {
  const ta = evaluation.task_analysis;
  const summary: EvaluationSummary | null = evaluation.summary;

  return (
    <div className="flex flex-col gap-6">
      {/* 任務分析 */}
      <div className="flex flex-col gap-2">
        <SectionLabel>任務分析</SectionLabel>
        {ta ? (
          <>
            <p className="text-sm">{ta.summary}</p>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">意圖:{intentLabel(ta.intent)}</Badge>
              <Badge variant="secondary">
                複雜度:{complexityLabel(ta.complexity)}
              </Badge>
            </div>
          </>
        ) : (
          <span className="text-sm text-muted-foreground">(無任務分析)</span>
        )}
      </div>

      {summary ? (
        <>
          {/* 平均吻合度 + min–max 範圍 + 色階進度條 */}
          <div className="flex flex-col gap-2">
            <div className="flex items-baseline justify-between">
              <SectionLabel>平均吻合度</SectionLabel>
              <span className="text-sm text-muted-foreground">
                範圍 {formatFitPercent(summary.min_fit_score)}–
                {formatFitPercent(summary.max_fit_score)}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="min-w-[3rem] text-lg font-semibold">
                {formatFitPercent(summary.avg_fit_score)}
              </span>
              <MetricBar score={summary.avg_fit_score} />
            </div>
          </div>

          {/* 推薦共識 */}
          <div className="flex flex-col gap-2">
            <SectionLabel>推薦共識</SectionLabel>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm font-medium">
                {summary.recommend_consensus.model ?? "(無共識推薦)"}
              </span>
              {summary.recommend_consensus.tier && (
                <Badge variant="default">{summary.recommend_consensus.tier}</Badge>
              )}
              {/* 票數:眾數得票 / 評審成功數(分母用 succeeded_count,代表「有效推薦的裁判數」)*/}
              <span className="text-sm text-muted-foreground">
                {summary.recommend_consensus.votes}/{summary.succeeded_count} 票
              </span>
              {summary.recommend_consensus.is_split && (
                <Badge variant="secondary">分歧</Badge>
              )}
            </div>
          </div>

          {/* 自我偏好警示(ai_self_vote)*/}
          <div className="flex flex-col gap-2">
            <SectionLabel>自我偏好</SectionLabel>
            <div>
              {summary.self_vote_count > 0 ? (
                <Badge variant="warning">
                  {summary.self_vote_count} 位裁判推薦自家廠商
                </Badge>
              ) : (
                <Badge variant="success">無自我偏好</Badge>
              )}
            </div>
          </div>

          {/* 評審完成度(部分成功)*/}
          {summary.succeeded_count < summary.judge_count && (
            <div className="flex flex-col gap-2">
              <SectionLabel>評審完成度</SectionLabel>
              <div>
                <Badge variant="warning">
                  部分成功({summary.succeeded_count}/{summary.judge_count})
                </Badge>
              </div>
            </div>
          )}
        </>
      ) : (
        // 型別上 evaluated 時 summary 仍可空,防呆不爆
        <span className="text-sm text-muted-foreground">(無彙總資料)</span>
      )}
    </div>
  );
}

export function AiAnalysisSection({ uid }: { uid: string }) {
  const [evaluation, setEvaluation] = React.useState<EvaluationResult | null>(
    null
  );
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!uid) return;
    let alive = true;
    setLoading(true);
    setError(null);
    apiClient
      .get<EvaluationResultResponse>(API_ENDPOINTS.aiEvaluationByUsageLog(uid))
      .then((data) => {
        if (alive) setEvaluation(data.evaluation);
      })
      .catch((err) => {
        if (alive) {
          setError(
            err instanceof ApiError ? err.localizedDetail : "載入 AI 分析失敗"
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

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">AI 分析</h2>
      <Card>
        <CardContent className="pt-6">
          {loading ? (
            // loading:Skeleton
            <div className="flex flex-col gap-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : error ? (
            // fetch error:顯示錯誤但不阻斷整頁
            <span className="text-sm text-destructive">{error}</span>
          ) : evaluation === null ? (
            // 狀態機 1:未評審
            <div className="rounded-lg bg-muted/50 p-4 text-sm text-muted-foreground">
              尚未評審(可能未啟用 AI 評審 <code>AI_EVAL_ENABLED=false</code>,或尚未輪到此筆)
            </div>
          ) : evaluation.status === "pending" ? (
            // 狀態機 2:評審中
            <div className="rounded-lg bg-muted/50 p-4 text-sm text-muted-foreground">
              評審中,稍候再回來查看結果。
            </div>
          ) : evaluation.status === "error" ? (
            // 狀態機 3:評審失敗(不顯示彙總)
            <div className="rounded-lg bg-destructive/10 p-4 text-sm text-destructive">
              評審失敗,本筆無可用的 AI 分析結果。
            </div>
          ) : (
            // 狀態機 4:已評審 → 基礎摘要卡
            <EvaluatedSummary evaluation={evaluation} />
          )}
        </CardContent>
      </Card>
    </section>
  );
}
