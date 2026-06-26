"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { PageTitle } from "@/components/common/PageTitle";
import { PageHint } from "@/components/common/PageHint";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { EmptyState } from "@/components/common/EmptyState";
import { useDialog } from "@/lib/dialog";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { formatUSD } from "@/lib/utils/format";
import {
  winnerLabel,
  winnerTone,
  formatConfidencePercent,
} from "@/lib/ai-eval-labels";
import { useAppSelector } from "@/store/hooks";
import type { Paginated, RerunOverviewItem } from "@/types/api";

// AI 判決總覽頁(跨 log):彙整所有 challenger 真實重跑 + 對比裁決,最新優先、分頁。
// 點任一列 → 進該 usage-log 明細頁看完整 AI 分析(原 v2.0.4 專頁;落 sidebar「AI 分析」)。

// winnerTone → Badge variant(對齊 usage-logs 明細頁 AiRerunSection 集中映射)。
const WINNER_BADGE_VARIANT: Record<
  ReturnType<typeof winnerTone>,
  React.ComponentProps<typeof Badge>["variant"]
> = {
  original: "secondary",
  challenger: "success",
  tie: "warning",
  none: "secondary",
};

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

const PAGE_SIZE = 20;

export default function AiVerdictsPage() {
  const router = useRouter();
  const { showDialog } = useDialog();
  const role = useAppSelector((s) => s.auth.actor?.role);

  const [items, setItems] = React.useState<RerunOverviewItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [loading, setLoading] = React.useState(true);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<Paginated<RerunOverviewItem>>(
        API_ENDPOINTS.aiRerunsOverview,
        { query: { page, size: PAGE_SIZE } }
      );
      setItems(data.items);
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
        彙整所有 usage log 經 AI 評審推薦後的 challenger「真實重跑 + 對比裁決」結果,最新優先。
        點任一列可進該筆用量紀錄明細頁,檢視完整 AI 分析與裁決理由。
      </PageHint>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex flex-col gap-2 p-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="py-10">
              <EmptyState
                title="尚無 AI 判決"
                description="目前沒有任何 challenger 重跑對比結果。當評審推薦了與原模型不同的模型、且重跑總開關開啟時,結果會在此彙整。"
              />
            </div>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>執行時間</TH>
                  <TH>原模型 → Challenger</TH>
                  <TH>裁決</TH>
                  <TH className="text-right">信心</TH>
                  <TH className="text-right">成本Δ(vs 原)</TH>
                  <TH className="text-right">延遲</TH>
                </TR>
              </THead>
              <TBody>
                {items.map((it) => {
                  const failed = it.status !== "success";
                  const unjudged = !failed && it.compare_winner === null;
                  return (
                    <TR
                      key={`${it.usage_log_uid}-${it.rerun_model}-${it.triggered_at}`}
                      className="cursor-pointer hover:bg-muted/40"
                      onClick={() =>
                        router.push(`/usage-logs/${it.usage_log_uid}`)
                      }
                    >
                      <TD className="whitespace-nowrap">
                        {formatDateTime(it.triggered_at)}
                      </TD>
                      <TD>
                        <span className="flex flex-wrap items-center gap-1 font-mono text-xs">
                          <span className="text-muted-foreground">
                            {it.original_model}
                          </span>
                          <span className="text-muted-foreground">→</span>
                          <span className="font-medium">{it.rerun_model}</span>
                        </span>
                      </TD>
                      <TD>
                        {failed ? (
                          <Badge variant="destructive">重跑失敗</Badge>
                        ) : unjudged ? (
                          <Badge variant="secondary">已重跑·未裁決</Badge>
                        ) : (
                          <Badge
                            variant={
                              WINNER_BADGE_VARIANT[
                                winnerTone(it.compare_winner!)
                              ]
                            }
                          >
                            {winnerLabel(it.compare_winner!)}
                          </Badge>
                        )}
                      </TD>
                      <TD className="text-right">
                        {failed || unjudged
                          ? "—"
                          : formatConfidencePercent(it.compare_score)}
                      </TD>
                      <TD
                        className={`text-right font-mono ${costDeltaClass(
                          it.cost_delta_usd
                        )}`}
                      >
                        {failed ? "—" : formatCostDelta(it.cost_delta_usd)}
                      </TD>
                      <TD className="text-right font-mono">
                        {it.latency_ms === null ? "—" : `${it.latency_ms} ms`}
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {!loading && items.length > 0 && (
        <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
          <span>
            共 {total} 筆 · 第 {page} / {totalPages} 頁
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
