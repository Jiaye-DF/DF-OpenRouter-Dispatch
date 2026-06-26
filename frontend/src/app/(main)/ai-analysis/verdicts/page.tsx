"use client";

import * as React from "react";
import { PageTitle } from "@/components/common/PageTitle";
import { PageHint } from "@/components/common/PageHint";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { useDialog } from "@/lib/dialog";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { formatUSD } from "@/lib/utils/format";
import {
  winnerLabel,
  winnerTone,
  formatConfidencePercent,
  verdictDistributionLabel,
} from "@/lib/ai-eval-labels";
import { useAppSelector } from "@/store/hooks";
import type {
  RerunOverviewPage,
  RerunGroup,
  RerunRecommendation,
  RerunStats,
} from "@/types/api";

// AI 判決總覽頁(/ai-analysis/verdicts,admin):依用量紀錄分組,並排呈現
// 「原模型 vs 推薦模型1/2/3 真實輸出原文」+ 成本Δ + 裁決 + 頁頂裁決分布統計。
// 核心紅線:本頁明細全由 aiRerunsOverview API 一次帶足自含渲染,
// 嚴禁任何連回用量紀錄頁的連結 / 導頁(對齊 propose §6.1 決議 #12)。

// winnerTone → Badge variant(集中映射)。
const WINNER_BADGE_VARIANT: Record<
  ReturnType<typeof winnerTone>,
  React.ComponentProps<typeof Badge>["variant"]
> = {
  original: "secondary",
  challenger: "success",
  tie: "warning",
  none: "secondary",
};

// 頁頂統計卡:依 stats 欄位排序顯示(label 取自 ai-eval-labels,禁硬編)。
const STATS_FIELDS: { key: keyof RerunStats; labelKey: string }[] = [
  { key: "total_recommendations", labelKey: "total" },
  { key: "keep_count", labelKey: "keep" },
  { key: "swap_count", labelKey: "swap" },
  { key: "tie_count", labelKey: "tie" },
  { key: "unjudged_count", labelKey: "unjudged" },
  { key: "failed_count", labelKey: "failed" },
];

// 成本Δ 顏色:< 0(更省)=綠;> 0(更貴)=紅;= 0 / 無資料=中性。
function costDeltaClass(delta: string | null): string {
  if (delta === null) return "text-muted-foreground";
  const n = Number(delta);
  if (!Number.isFinite(n) || n === 0) return "text-muted-foreground";
  return n < 0 ? "text-emerald-600" : "text-destructive";
}

// 成本Δ 顯示:正值補 +(負值 toFixed 自帶 -),null → em dash。
function formatCostDelta(delta: string | null): string {
  if (delta === null) return "—";
  const n = Number(delta);
  if (!Number.isFinite(n)) return "—";
  return `${n > 0 ? "+" : ""}${formatUSD(delta)}`;
}

// ISO → 顯示字串(對齊 04-datetime.md:DB 存 UTC+8 wall-clock,禁 toLocaleString;
// utils/datetime.ts 尚未建立,暫以正規表示式切字串,已記入 fixed.md 待後續抽 util)。
function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})/);
  return m ? `${m[1]}/${m[2]}/${m[3]} ${m[4]}:${m[5]}:${m[6]}` : iso;
}

// 推薦模型列狀態:重跑失敗 / 已重跑·未裁決(子開關關)/ 已裁決。
function recState(
  rec: RerunRecommendation,
): "failed" | "unjudged" | "judged" {
  if (rec.status !== "success") return "failed";
  if (rec.compare_winner === null) return "unjudged";
  return "judged";
}

// 該組彙總裁決:統計推薦模型裁決分布,挑出多數者組成「n/總 <label>」。
// 全失敗 / 全未裁決 → 對應狀態文案;無推薦 → null。
function summaryVerdict(group: RerunGroup): {
  text: string;
  variant: React.ComponentProps<typeof Badge>["variant"];
} | null {
  const recs = group.recommendations;
  if (recs.length === 0) return null;
  const counts: Record<string, number> = {};
  let failed = 0;
  let unjudged = 0;
  for (const rec of recs) {
    const st = recState(rec);
    if (st === "failed") failed += 1;
    else if (st === "unjudged") unjudged += 1;
    else counts[rec.compare_winner!] = (counts[rec.compare_winner!] ?? 0) + 1;
  }
  const judged = Object.entries(counts);
  if (judged.length > 0) {
    judged.sort((a, b) => b[1] - a[1]);
    const [winner, n] = judged[0];
    return {
      text: `${n}/${recs.length} ${winnerLabel(winner)}`,
      variant: WINNER_BADGE_VARIANT[winnerTone(winner)],
    };
  }
  if (failed === recs.length) return { text: "全數重跑失敗", variant: "destructive" };
  if (unjudged > 0) return { text: "已重跑·未裁決", variant: "secondary" };
  return { text: "已重跑·未裁決", variant: "secondary" };
}

const PAGE_SIZE = 10;

// 真實輸出原文區塊(原模型 / 推薦模型共用):max-h + 內部捲動,null 顯示佔位文案。
function OutputText({
  text,
  emptyHint,
}: {
  text: string | null;
  emptyHint: string;
}) {
  if (!text) {
    return (
      <p className="text-sm italic text-muted-foreground">{emptyHint}</p>
    );
  }
  return (
    <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted/40 p-3 text-sm leading-relaxed">
      {text}
    </pre>
  );
}

// 單一比較欄(原模型欄 or 推薦模型欄)。原模型欄不帶 recommendation。
function CompareColumn({
  modelKey,
  tierLabel,
  outputText,
  emptyHint,
  rec,
}: {
  modelKey: string;
  tierLabel: string;
  outputText: string | null;
  emptyHint: string;
  rec?: RerunRecommendation;
}) {
  const state = rec ? recState(rec) : null;
  return (
    <div className="flex flex-col rounded-lg border border-border bg-card">
      <div className="flex flex-wrap items-center gap-2 border-b border-border p-3">
        <span className="break-all font-mono text-sm font-medium">
          {modelKey}
        </span>
        <Badge variant="secondary">{tierLabel}</Badge>
      </div>
      <div className="flex-1 p-3">
        <OutputText text={outputText} emptyHint={emptyHint} />
      </div>
      {rec && (
        <div className="flex flex-col gap-2 border-t border-border p-3 text-sm">
          {state === "failed" ? (
            <Badge variant="destructive" className="self-start">
              重跑失敗
              {rec.error_code ? `(${rec.error_code})` : ""}
            </Badge>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="text-muted-foreground">成本</span>
                <span className="font-mono">{formatUSD(rec.cost_usd)}</span>
                <span className="text-muted-foreground">Δ</span>
                <span className={`font-mono ${costDeltaClass(rec.cost_delta_usd)}`}>
                  {formatCostDelta(rec.cost_delta_usd)}
                </span>
                <span className="text-muted-foreground">延遲</span>
                <span className="font-mono">
                  {rec.latency_ms === null ? "—" : `${rec.latency_ms} ms`}
                </span>
              </div>
              {state === "unjudged" ? (
                <Badge variant="secondary" className="self-start">
                  已重跑·未裁決
                </Badge>
              ) : (
                <div className="flex flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge
                      variant={WINNER_BADGE_VARIANT[winnerTone(rec.compare_winner!)]}
                    >
                      {winnerLabel(rec.compare_winner!)}
                    </Badge>
                    <span className="text-muted-foreground">
                      信心 {formatConfidencePercent(rec.compare_score)}
                    </span>
                  </div>
                  {rec.compare_reason && (
                    <p className="text-muted-foreground">{rec.compare_reason}</p>
                  )}
                  {rec.compare_judge_model && (
                    <p className="text-xs text-muted-foreground">
                      裁決模型:
                      <span className="font-mono">{rec.compare_judge_model}</span>
                    </p>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// 一組分組 Card(可展開 / 收合)。
function GroupCard({ group }: { group: RerunGroup }) {
  const [open, setOpen] = React.useState(false);
  const summary = summaryVerdict(group);
  const recCount = group.recommendations.length;

  return (
    <Card>
      <CardContent className="p-0">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex min-h-[44px] w-full flex-col gap-2 p-4 text-left hover:bg-muted/40 md:flex-row md:items-center md:justify-between"
        >
          <span className="flex flex-wrap items-center gap-2 font-mono text-sm">
            <span className="font-medium">{group.original_model}</span>
            <span className="text-muted-foreground">→ 推薦 {recCount} 個</span>
          </span>
          <span className="flex flex-wrap items-center gap-3 text-sm">
            {summary && (
              <Badge variant={summary.variant}>{summary.text}</Badge>
            )}
            <span className="text-muted-foreground">
              {formatDateTime(group.evaluated_at)}
            </span>
            <span aria-hidden className="text-muted-foreground">
              {open ? "收合 ▲" : "展開 ▼"}
            </span>
          </span>
        </button>

        {open && (
          <div className="border-t border-border p-4">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              <CompareColumn
                modelKey={group.original_model}
                tierLabel="原始"
                outputText={group.original_output_text}
                emptyHint="無原始輸出快照"
              />
              {group.recommendations.map((rec, i) => (
                <CompareColumn
                  key={`${rec.rerun_model}-${rec.triggered_at}-${i}`}
                  modelKey={rec.rerun_model}
                  tierLabel="推薦"
                  outputText={rec.output_text}
                  emptyHint="無輸出"
                  rec={rec}
                />
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function AiVerdictsPage() {
  const { showDialog } = useDialog();
  const role = useAppSelector((s) => s.auth.actor?.role);

  const [groups, setGroups] = React.useState<RerunGroup[]>([]);
  const [stats, setStats] = React.useState<RerunStats | null>(null);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [loading, setLoading] = React.useState(true);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<RerunOverviewPage>(
        API_ENDPOINTS.aiRerunsOverview,
        { query: { page, size: PAGE_SIZE } }
      );
      setGroups(data.items);
      setStats(data.stats);
      setTotal(data.total);
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "載入失敗",
          message: err.localizedDetail,
        });
      }
    } finally {
      setLoading(false);
    }
  }, [page, showDialog]);

  React.useEffect(() => {
    if (role === "admin") load();
  }, [load, role]);

  if (role && role !== "admin") {
    return (
      <>
        <PageTitle title="AI 判決總覽" />
        <Card>
          <CardContent className="py-10">
            <EmptyState title="權限不足" description="此頁僅限管理員檢視。" />
          </CardContent>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageTitle title="AI 判決總覽" />
      <PageHint>
        依用量紀錄分組,並排呈現「原模型 vs AI 推薦模型」的真實輸出原文、成本Δ、對比裁決與信心。
        展開任一組即可直接比較;明細全在本頁,不需離開。
      </PageHint>

      {/* 頁頂裁決分布統計列 */}
      {loading ? (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : stats ? (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {STATS_FIELDS.map(({ key, labelKey }) => (
            <Card key={key}>
              <CardContent className="flex flex-col gap-1 p-4">
                <span className="text-sm text-muted-foreground">
                  {verdictDistributionLabel(labelKey)}
                </span>
                <span className="text-2xl font-semibold tabular-nums">
                  {stats[key]}
                </span>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}

      {/* 主體:分組 Card 列表 */}
      {loading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : groups.length === 0 ? (
        <Card>
          <CardContent className="py-10">
            <EmptyState
              title="尚無 AI 判決"
              description="目前沒有任何 AI 推薦模型的真實重跑對比結果。當評審推薦了與原模型不同的模型、且重跑總開關開啟時,結果會在此彙整。"
            />
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {groups.map((group) => (
            <GroupCard key={group.usage_log_uid} group={group} />
          ))}
        </div>
      )}

      {!loading && groups.length > 0 && (
        <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
          <span>
            共 {total} 組 · 第 {page} / {totalPages} 頁
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              上一頁
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              下一頁
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
