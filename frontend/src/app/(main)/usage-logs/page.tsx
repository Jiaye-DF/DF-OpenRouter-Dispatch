"use client";

import * as React from "react";
import { PageTitle } from "@/components/common/PageTitle";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { EmptyState } from "@/components/common/EmptyState";
import { useDialog } from "@/lib/dialog";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import type { Department, Paginated, UsageLog } from "@/types/api";

// 用量紀錄頁：支援部門 / 模型 / 狀態 / 時間 篩選

export default function UsageLogsPage() {
  const { showDialog } = useDialog();
  const [items, setItems] = React.useState<UsageLog[]>([]);
  const [depts, setDepts] = React.useState<Department[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [page, setPage] = React.useState(1);
  const [total, setTotal] = React.useState(0);
  const size = 20;

  const [filters, setFilters] = React.useState({
    department_uid: "",
    model: "",
    status: "",
    from: "",
    to: "",
  });

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const query: Record<string, string | number> = { page, size };
      if (filters.department_uid) query.department_uid = filters.department_uid;
      if (filters.model) query.model = filters.model;
      if (filters.status) query.status = filters.status;
      if (filters.from) query.from = filters.from;
      if (filters.to) query.to = filters.to;
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
    load();
  }, [load]);

  React.useEffect(() => {
    // 部門僅載入一次
    apiClient
      .get<Paginated<Department>>(API_ENDPOINTS.departments, {
        query: { page: 1, size: 200 },
      })
      .then((d) => setDepts(d.items))
      .catch(() => {});
  }, []);

  const deptName = (uid: string) =>
    depts.find((d) => d.department_uid === uid)?.name ?? uid;

  const totalPages = Math.max(1, Math.ceil(total / size));

  return (
    <>
      <PageTitle
        title="用量紀錄"
        description="代理呼叫每次皆會寫入一筆，含失敗情況"
      />
      <Card>
        <CardContent className="pt-6 flex flex-col gap-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="flex flex-col gap-1">
              <Label className="text-sm">部門</Label>
              <select
                className="h-9 rounded-xl border border-border bg-background px-3 text-sm hover:cursor-pointer"
                value={filters.department_uid}
                onChange={(e) =>
                  setFilters({ ...filters, department_uid: e.target.value })
                }
              >
                <option value="">全部</option>
                {depts.map((d) => (
                  <option key={d.department_uid} value={d.department_uid}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-sm">模型</Label>
              <Input
                className="h-9"
                value={filters.model}
                onChange={(e) => setFilters({ ...filters, model: e.target.value })}
                placeholder="anthropic/..."
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-sm">狀態</Label>
              <select
                className="h-9 rounded-xl border border-border bg-background px-3 text-sm hover:cursor-pointer"
                value={filters.status}
                onChange={(e) =>
                  setFilters({ ...filters, status: e.target.value })
                }
              >
                <option value="">全部</option>
                <option value="success">success</option>
                <option value="error">error</option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-sm">起始</Label>
              <Input
                type="datetime-local"
                className="h-9"
                value={filters.from}
                onChange={(e) => setFilters({ ...filters, from: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-sm">結束</Label>
              <Input
                type="datetime-local"
                className="h-9"
                value={filters.to}
                onChange={(e) => setFilters({ ...filters, to: e.target.value })}
              />
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <Button
              variant="outline"
              onClick={() =>
                setFilters({
                  department_uid: "",
                  model: "",
                  status: "",
                  from: "",
                  to: "",
                })
              }
            >
              清除
            </Button>
            <Button onClick={() => { setPage(1); load(); }}>套用篩選</Button>
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
                  <TH>時間</TH>
                  <TH>部門</TH>
                  <TH>模型</TH>
                  <TH className="text-right">Prompt</TH>
                  <TH className="text-right">Completion</TH>
                  <TH className="text-right">Total</TH>
                  <TH className="text-right">Cost USD</TH>
                  <TH className="text-right">Latency</TH>
                  <TH>狀態</TH>
                </TR>
              </THead>
              <TBody>
                {items.map((log) => (
                  <TR key={log.usage_log_uid}>
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
                    <TD className="text-right">
                      ${Number(log.cost_usd).toFixed(4)}
                    </TD>
                    <TD className="text-right">{log.latency_ms} ms</TD>
                    <TD>
                      <Badge
                        variant={log.status === "success" ? "success" : "destructive"}
                      >
                        {log.status}
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
