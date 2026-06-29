"use client";

import * as React from "react";
import { PageTitle } from "@/components/common/PageTitle";
import { PageHint } from "@/components/common/PageHint";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/EmptyState";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
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
  RerunUsageLogInfo,
} from "@/types/api";

// AI 判決總覽頁(/ai-analysis/verdicts,admin):分層顯示。
//   第一層 — 頁頂裁決分布統計列(沿用)。
//   第二層 — 每筆 usage_log 一列(可展開),展開後僅列出該組推薦模型精簡表格,
//            「不」直接 render 輸出原文(要看再點 [查看])。
//   第三層 — Dialog(點某列 [查看] 開啟):任務輸入 + 原模型/推薦模型並排輸出 + 裁決理由。
// 核心紅線:明細全由 aiRerunsOverview API 一次帶足自含渲染,
// 嚴禁任何連回用量紀錄頁的連結 / 導頁(對齊 propose §6.1 決議 #12)。
// usage_log uid 只當顯示文字 / 複製,不做成連結。

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

// 推薦模型列裁決 Badge:失敗→重跑失敗(不外顯 error_code);未裁決→已重跑·未裁決;已裁決→winnerLabel/winnerTone。
function recVerdictBadge(rec: RerunRecommendation): {
  text: string;
  variant: React.ComponentProps<typeof Badge>["variant"];
} {
  const st = recState(rec);
  if (st === "failed") {
    return { text: "重跑失敗", variant: "destructive" };
  }
  if (st === "unjudged") {
    return { text: "已重跑·未裁決", variant: "secondary" };
  }
  return {
    text: winnerLabel(rec.compare_winner!),
    variant: WINNER_BADGE_VARIANT[winnerTone(rec.compare_winner!)],
  };
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
  for (const rec of recs) {
    const st = recState(rec);
    if (st === "failed") failed += 1;
    else if (st === "judged")
      counts[rec.compare_winner!] = (counts[rec.compare_winner!] ?? 0) + 1;
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
  return { text: "已重跑·未裁決", variant: "secondary" };
}

const PAGE_SIZE = 10;

// 第三層 Dialog 開啟狀態:鎖定「哪一組 + 該組第幾個推薦模型」。
type ViewTarget = { group: RerunGroup; rec: RerunRecommendation } | null;

// 真實輸出原文區塊(Dialog 內,原模型 / 推薦模型共用):max-h + 內部捲動,null 顯示佔位文案。
function OutputText({
  text,
  emptyHint,
}: {
  text: string | null;
  emptyHint: string;
}) {
  if (!text) {
    return <p className="text-sm italic text-muted-foreground">{emptyHint}</p>;
  }
  return (
    <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted/40 p-3 text-sm leading-relaxed">
      {text}
    </pre>
  );
}

// Dialog 內:用量紀錄基礎資訊精簡 label/value 網格(「這是哪一筆」識別資訊;非連結)。
// 純顯示,嚴禁任何連回用量紀錄頁 / 導頁。null → 佔位文案。
function UsageLogInfoGrid({ info }: { info: RerunUsageLogInfo | null }) {
  if (!info) {
    return (
      <p className="text-sm italic text-muted-foreground">
        無用量紀錄基礎資訊(歷史紀錄)
      </p>
    );
  }
  const cells: { label: string; node: React.ReactNode }[] = [
    { label: "編號", node: <span className="font-mono">#{info.pid}</span> },
    { label: "呼叫時間", node: formatDateTime(info.created_at) },
    {
      label: "模型",
      node: <span className="break-all font-mono">{info.model}</span>,
    },
    {
      label: "狀態",
      node: (
        <Badge variant={info.status === "success" ? "success" : "destructive"}>
          {info.status === "success" ? "成功" : "失敗"}
        </Badge>
      ),
    },
    {
      label: "Token(輸入/回覆/合計)",
      node: (
        <span className="font-mono">
          {info.prompt_tokens} / {info.completion_tokens} / {info.total_tokens}
        </span>
      ),
    },
    {
      label: "成本",
      node: <span className="font-mono">{formatUSD(info.cost_usd)}</span>,
    },
    {
      label: "延遲",
      node: <span className="font-mono">{info.latency_ms} ms</span>,
    },
    { label: "工具", node: info.used_tools ? "有用工具" : "未用工具" },
  ];
  if (info.error_code) {
    cells.push({
      label: "錯誤碼",
      node: <span className="break-all font-mono">{info.error_code}</span>,
    });
  }
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
      {cells.map((c) => (
        <div key={c.label} className="flex flex-col gap-0.5">
          <dt className="text-xs text-muted-foreground">{c.label}</dt>
          <dd className="text-sm">{c.node}</dd>
        </div>
      ))}
    </dl>
  );
}

// 第二層展開後:單一推薦模型精簡列(表格 row)。不直接 render 輸出原文。
function RecRow({
  rec,
  onView,
}: {
  rec: RerunRecommendation;
  onView: () => void;
}) {
  const verdict = recVerdictBadge(rec);
  const judged = recState(rec) === "judged";
  return (
    <tr className="border-b border-border last:border-0 align-top">
      <td className="whitespace-nowrap px-3 py-2 font-mono text-sm">
        {rec.rerun_model}
      </td>
      <td className="whitespace-nowrap px-3 py-2 font-mono text-sm text-muted-foreground">
        {rec.recommended_by ?? "—"}
      </td>
      <td className="whitespace-nowrap px-3 py-2">
        <Badge variant={verdict.variant}>{verdict.text}</Badge>
      </td>
      <td className="whitespace-nowrap px-3 py-2 text-sm">
        {judged ? formatConfidencePercent(rec.compare_score) : "—"}
      </td>
      <td
        className={`whitespace-nowrap px-3 py-2 text-right font-mono text-sm ${costDeltaClass(rec.cost_delta_usd)}`}
      >
        {formatCostDelta(rec.cost_delta_usd)}
      </td>
      <td className="whitespace-nowrap px-3 py-2 text-right font-mono text-sm">
        {rec.latency_ms === null ? "—" : `${rec.latency_ms} ms`}
      </td>
      <td className="whitespace-nowrap px-3 py-2 text-right">
        <Button
          variant="outline"
          size="sm"
          className="min-h-[44px]"
          onClick={onView}
        >
          查看
        </Button>
      </td>
    </tr>
  );
}

// 第二層:一筆 usage_log = 一列(可展開)。收合精簡;展開列出推薦模型精簡表格。
function GroupRow({
  group,
  onView,
}: {
  group: RerunGroup;
  onView: (rec: RerunRecommendation) => void;
}) {
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
            {group.usage_log_info && (
              <span className="text-muted-foreground">
                #{group.usage_log_info.pid}
              </span>
            )}
            <span className="font-medium">{group.original_model}</span>
            <span className="text-muted-foreground">→ 推薦 {recCount} 個</span>
          </span>
          <span className="flex flex-wrap items-center gap-3 text-sm">
            {summary && <Badge variant={summary.variant}>{summary.text}</Badge>}
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
            {recCount === 0 ? (
              <p className="text-sm italic text-muted-foreground">
                此用量紀錄沒有 AI 推薦模型。
              </p>
            ) : (
              <div className="-mx-1 overflow-x-auto">
                {/* 欄位各取自然寬度水平排開(w-max),至少撐滿容器(min-w-full);
                    總寬超出容器時由外層 overflow-x-auto 水平滾動,欄位一律不換行。 */}
                <table className="w-max min-w-full border-collapse text-left">
                  <thead>
                    <tr className="whitespace-nowrap border-b border-border text-xs text-muted-foreground">
                      <th className="px-3 py-2 font-medium">推薦模型</th>
                      <th className="px-3 py-2 font-medium">推薦者</th>
                      <th className="px-3 py-2 font-medium">裁決</th>
                      <th className="px-3 py-2 font-medium">信心</th>
                      <th className="px-3 py-2 text-right font-medium">成本Δ</th>
                      <th className="px-3 py-2 text-right font-medium">延遲</th>
                      <th className="px-3 py-2 text-right font-medium">輸出</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.recommendations.map((rec, i) => (
                      <RecRow
                        key={`${rec.rerun_model}-${rec.triggered_at}-${i}`}
                        rec={rec}
                        onView={() => onView(rec)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// 第三層:Dialog 內容。對應某推薦模型 → 顯示完整對照(輸入 + 並排輸出 + 裁決理由)。
function VerdictDialog({
  target,
  onClose,
}: {
  target: ViewTarget;
  onClose: () => void;
}) {
  if (!target) return null;
  const { group, rec } = target;
  const verdict = recVerdictBadge(rec);
  const judged = recState(rec) === "judged";

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>輸出對照</DialogTitle>
          <div className="flex flex-col gap-2 pt-1 text-sm">
            <div className="flex flex-wrap items-center gap-2 font-mono">
              <span className="font-medium">{group.original_model}</span>
              <span aria-hidden className="text-muted-foreground">
                →
              </span>
              <span className="font-medium">{rec.rerun_model}</span>
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="text-muted-foreground">
                推薦者:
                <span className="font-mono">{rec.recommended_by ?? "—"}</span>
              </span>
              <Badge variant={verdict.variant}>{verdict.text}</Badge>
              {judged && (
                <span className="text-muted-foreground">
                  信心 {formatConfidencePercent(rec.compare_score)}
                </span>
              )}
            </div>
          </div>
        </DialogHeader>

        <div className="mt-4 flex flex-col gap-4">
          {/* 用量紀錄基礎資訊(這是哪一筆) */}
          <section className="flex flex-col gap-1.5 rounded-lg border border-border bg-muted/30 p-3">
            <h3 className="text-sm font-semibold">用量紀錄基礎資訊</h3>
            <UsageLogInfoGrid info={group.usage_log_info} />
          </section>

          {/* 任務輸入 */}
          <section className="flex flex-col gap-1.5">
            <h3 className="text-sm font-semibold">任務輸入</h3>
            <OutputText
              text={group.original_input_text}
              emptyHint="無輸入快照"
            />
          </section>

          {/* 並排兩欄輸出(桌機並排、手機堆疊) */}
          <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <h3 className="break-all text-sm font-semibold">
                原模型輸出
                <span className="ml-1 font-mono text-xs text-muted-foreground">
                  {group.original_model}
                </span>
              </h3>
              <OutputText
                text={group.original_output_text}
                emptyHint="無原始輸出快照"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <h3 className="break-all text-sm font-semibold">
                推薦模型輸出
                <span className="ml-1 font-mono text-xs text-muted-foreground">
                  {rec.rerun_model}
                </span>
              </h3>
              <OutputText
                text={rec.output_text}
                emptyHint={
                  recState(rec) === "failed"
                    ? "重跑失敗,無推薦模型輸出"
                    : "無輸出"
                }
              />
            </div>
          </section>

          {/* 裁決理由 + 裁決模型 */}
          <section className="flex flex-col gap-1.5">
            <h3 className="text-sm font-semibold">裁決理由</h3>
            {recState(rec) === "failed" ? (
              <p className="text-sm text-muted-foreground">
                此推薦模型重跑失敗,未進行裁決。上方保留原模型輸出供對照。
              </p>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">
                  {rec.compare_reason ?? "無"}
                </p>
                {rec.compare_judge_model && (
                  <p className="text-xs text-muted-foreground">
                    裁決模型:
                    <span className="font-mono">{rec.compare_judge_model}</span>
                  </p>
                )}
              </>
            )}
          </section>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            關閉
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
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
  const [viewTarget, setViewTarget] = React.useState<ViewTarget>(null);
  // 編號(pid)排序方向(預設 desc 大→小)+ 編號精確搜尋。
  const [order, setOrder] = React.useState<"desc" | "asc">("desc");
  const [pidSearch, setPidSearch] = React.useState("");

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const query: Record<string, string | number> = {
        page,
        size: PAGE_SIZE,
        order,
      };
      if (pidSearch.trim()) query.pid = pidSearch.trim();
      const data = await apiClient.get<RerunOverviewPage>(
        API_ENDPOINTS.aiRerunsOverview,
        { query }
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
  }, [page, order, pidSearch, showDialog]);

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
        依用量紀錄分組,精簡分層呈現「原模型 vs AI 推薦模型」的對比裁決、成本Δ 與延遲。
        展開任一組看推薦模型清單,點 [查看] 開啟對照視窗看任務輸入與兩側完整輸出;明細全在本頁,不需離開。
      </PageHint>

      {/* 工具列:編號搜尋 + 編號排序切換(對應用量紀錄編號 #pid) */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Input
          type="number"
          inputMode="numeric"
          placeholder="搜尋編號"
          className="h-9 w-32"
          value={pidSearch}
          onChange={(e) => {
            setPidSearch(e.target.value);
            setPage(1);
          }}
        />
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setOrder((o) => (o === "desc" ? "asc" : "desc"));
            setPage(1);
          }}
          title="切換編號排序"
        >
          編號 {order === "desc" ? "▼ 大→小" : "▲ 小→大"}
        </Button>
      </div>

      {/* 第一層 — 頁頂裁決分布統計列 */}
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

      {/* 第二層 — 每筆 usage_log 一列(可展開) */}
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
            <GroupRow
              key={group.usage_log_uid}
              group={group}
              onView={(rec) => setViewTarget({ group, rec })}
            />
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

      {/* 第三層 — Dialog(本地管理 open state) */}
      <VerdictDialog target={viewTarget} onClose={() => setViewTarget(null)} />
    </>
  );
}
