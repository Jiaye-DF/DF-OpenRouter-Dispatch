"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { PageTitle } from "@/components/common/PageTitle";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { FilterChip } from "@/components/ui/FilterChip";
import { Combobox } from "@/components/ui/Combobox";
import { EmptyState } from "@/components/common/EmptyState";
import { useDialog } from "@/lib/dialog";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { formatUSD } from "@/lib/utils/format";
import { useAppSelector } from "@/store/hooks";
import type { Department, Model, Paginated, UsageLog } from "@/types/api";

// 用量紀錄頁:部門 / 狀態 chip、模型 Combobox、時間區間快捷篩選

function fmtDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

// n 日前的日期字串(n=0 為今天)
function daysAgo(n: number): string {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - n);
  return fmtDate(d);
}

const RANGE_PRESETS = [3, 7, 30] as const;

const STATUS_OPTIONS = [
  { value: "", label: "全部" },
  { value: "success", label: "成功" },
  { value: "error", label: "失敗" },
] as const;

// 是否使用工具(tools,如 web search;可能觸發額外計費)
const TOOLS_OPTIONS = [
  { value: "", label: "全部" },
  { value: "true", label: "有用工具" },
  { value: "false", label: "未用工具" },
] as const;

const statusLabel = (s: string) =>
  s === "success" ? "成功" : s === "error" ? "失敗" : s;

export default function UsageLogsPage() {
  const router = useRouter();
  const { showDialog } = useDialog();
  const role = useAppSelector((s) => s.auth.actor?.role);
  const [items, setItems] = React.useState<UsageLog[]>([]);
  const [depts, setDepts] = React.useState<Department[]>([]);
  const [models, setModels] = React.useState<Model[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [page, setPage] = React.useState(1);
  const [total, setTotal] = React.useState(0);
  const size = 20;

  const [filters, setFilters] = React.useState({
    department_uid: "",
    model: "",
    status: "",
    used_tools: "", // "" | "true" | "false"
    order: "desc", // 編號排序方向:desc(大→小,預設)/ asc
    from: daysAgo(2), // 預設最近 3 日
    to: daysAgo(0),
  });

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const query: Record<string, string | number> = { page, size };
      if (filters.department_uid) query.department_uid = filters.department_uid;
      if (filters.model) query.model = filters.model;
      if (filters.status) query.status = filters.status;
      if (filters.used_tools) query.used_tools = filters.used_tools;
      query.order = filters.order;
      if (filters.from) query.from = `${filters.from}T00:00:00`;
      if (filters.to) query.to = `${filters.to}T23:59:59`;
      const data = await apiClient.get<Paginated<UsageLog>>(
        API_ENDPOINTS.usageLogs,
        { query }
      );
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "載入失敗", message: err.localizedDetail });
      }
    } finally {
      setLoading(false);
    }
  }, [page, filters, showDialog]);

  React.useEffect(() => {
    if (role === "admin") load();
  }, [load, role]);

  React.useEffect(() => {
    if (role !== "admin") return;
    // 部門 / 模型 清單僅載入一次,供篩選元件使用
    apiClient
      .get<Paginated<Department>>(API_ENDPOINTS.departments, {
        query: { page: 1, size: 200 },
      })
      .then((d) => setDepts(d.items))
      .catch(() => {});
    apiClient
      .get<Paginated<Model>>(API_ENDPOINTS.models)
      .then((d) => setModels(d.items))
      .catch(() => {});
  }, [role]);

  const deptName = (uid: string) =>
    depts.find((d) => d.department_uid === uid)?.name ?? uid;

  const modelOptions = React.useMemo(
    () => [
      { value: "", label: "全部模型" },
      ...models.map((m) => ({ value: m.model_key, label: m.model_key })),
    ],
    [models]
  );

  // 篩選變更一律回到第 1 頁;load 依賴 filters / page 變化自動重新查詢
  const update = (patch: Partial<typeof filters>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(1);
  };

  const setRange = (days: number) =>
    update({ from: daysAgo(days - 1), to: daysAgo(0) });

  const isPreset = (days: number) =>
    filters.from === daysAgo(days - 1) && filters.to === daysAgo(0);

  const reset = () =>
    update({
      department_uid: "",
      model: "",
      status: "",
      used_tools: "",
      from: daysAgo(2),
      to: daysAgo(0),
    });

  const totalPages = Math.max(1, Math.ceil(total / size));

  if (role !== "admin") {
    return (
      <>
        <PageTitle title="用量紀錄" />
        <Card>
          <CardContent className="pt-6">
            <EmptyState title="權限不足" description="本頁僅限 admin 存取" />
          </CardContent>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageTitle
        title="用量紀錄"
        description="代理呼叫每次皆會寫入一筆，含失敗情況"
      />
      <Card>
        <CardContent className="pt-6 flex flex-col gap-4">
          {/* 篩選區 — 依面向分列 */}
          <div className="flex flex-col gap-3 border-b border-border pb-4">
            {/* 部門 */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-20 shrink-0 text-sm text-muted-foreground">
                部門：
              </span>
              <FilterChip
                active={!filters.department_uid}
                onClick={() => update({ department_uid: "" })}
              >
                全部
              </FilterChip>
              {depts.map((d) => (
                <FilterChip
                  key={d.department_uid}
                  active={filters.department_uid === d.department_uid}
                  onClick={() => update({ department_uid: d.department_uid })}
                >
                  {d.name}
                </FilterChip>
              ))}
            </div>

            {/* 狀態 + 模型 — 同列水平排列 */}
            <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="w-20 shrink-0 text-sm text-muted-foreground">
                  狀態：
                </span>
                {STATUS_OPTIONS.map((o) => (
                  <FilterChip
                    key={o.value || "all"}
                    active={filters.status === o.value}
                    onClick={() => update({ status: o.value })}
                  >
                    {o.label}
                  </FilterChip>
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="shrink-0 text-sm text-muted-foreground">
                  模型：
                </span>
                <Combobox
                  className="w-64"
                  options={modelOptions}
                  value={filters.model}
                  onChange={(v) => update({ model: v })}
                  placeholder="全部模型"
                  searchPlaceholder="搜尋模型..."
                  emptyText="查無模型"
                />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="shrink-0 text-sm text-muted-foreground">
                  工具：
                </span>
                {TOOLS_OPTIONS.map((o) => (
                  <FilterChip
                    key={o.value || "all"}
                    active={filters.used_tools === o.value}
                    onClick={() => update({ used_tools: o.value })}
                  >
                    {o.label}
                  </FilterChip>
                ))}
              </div>
            </div>

            {/* 時間 */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-20 shrink-0 text-sm text-muted-foreground">
                按時間：
              </span>
              {RANGE_PRESETS.map((n) => (
                <FilterChip
                  key={n}
                  active={isPreset(n)}
                  onClick={() => setRange(n)}
                >
                  近 {n} 日
                </FilterChip>
              ))}
              <span className="ml-1 text-sm text-muted-foreground">起</span>
              <Input
                type="date"
                className="h-9 w-auto"
                value={filters.from}
                max={filters.to}
                onChange={(e) => update({ from: e.target.value })}
              />
              <span className="text-sm text-muted-foreground">迄</span>
              <Input
                type="date"
                className="h-9 w-auto"
                value={filters.to}
                min={filters.from}
                max={daysAgo(0)}
                onChange={(e) => update({ to: e.target.value })}
              />
              <Button
                variant="outline"
                size="sm"
                className="ml-auto"
                onClick={reset}
              >
                重設
              </Button>
            </div>
          </div>

          {loading ? (
            <div className="flex flex-col gap-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <EmptyState title="尚無用量紀錄" />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 hover:text-foreground"
                      onClick={() =>
                        update({ order: filters.order === "desc" ? "asc" : "desc" })
                      }
                      title="點擊切換編號排序"
                    >
                      編號 {filters.order === "desc" ? "▼" : "▲"}
                    </button>
                  </TH>
                  <TH>時間</TH>
                  <TH>部門</TH>
                  <TH>模型</TH>
                  <TH className="text-right">輸入 Token</TH>
                  <TH className="text-right">回覆 Token</TH>
                  <TH className="text-right">合計 Token</TH>
                  <TH className="text-right">花費 (USD)</TH>
                  <TH className="text-right">延遲</TH>
                  <TH>工具</TH>
                  <TH>狀態</TH>
                </TR>
              </THead>
              <TBody>
                {items.map((log) => (
                  <TR
                    key={log.usage_log_uid}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() =>
                      router.push(`/usage-logs/${log.usage_log_uid}`)
                    }
                  >
                    <TD className="font-mono text-sm text-muted-foreground whitespace-nowrap">
                      #{log.pid}
                    </TD>
                    <TD className="text-sm text-muted-foreground whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString()}
                    </TD>
                    <TD>{deptName(log.department_uid)}</TD>
                    <TD className="font-mono text-sm">{log.model}</TD>
                    <TD className="text-right">
                      {log.prompt_tokens.toLocaleString()}
                    </TD>
                    <TD className="text-right">
                      {log.completion_tokens.toLocaleString()}
                    </TD>
                    <TD className="text-right font-medium">
                      {log.total_tokens.toLocaleString()}
                    </TD>
                    <TD className="text-right font-mono text-sm">
                      {formatUSD(log.cost_usd)}
                    </TD>
                    <TD className="text-right">{log.latency_ms} ms</TD>
                    <TD>
                      {log.used_tools ? (
                        <Badge variant="secondary">工具</Badge>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TD>
                    <TD>
                      <Badge
                        variant={log.status === "success" ? "success" : "destructive"}
                      >
                        {statusLabel(log.status)}
                      </Badge>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {!loading && items.length > 0 && (
        <div className="flex items-center justify-between mt-4 text-sm text-muted-foreground">
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
