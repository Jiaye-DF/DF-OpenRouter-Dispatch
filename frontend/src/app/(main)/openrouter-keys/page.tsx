"use client";

import * as React from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { PageTitle } from "@/components/common/PageTitle";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingButton } from "@/components/common/LoadingButton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHint } from "@/components/common/PageHint";
import { useDialog } from "@/lib/dialog";
import { useConfirm } from "@/components/common/ConfirmDialog";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import type { Department, OpenRouterKey, Paginated } from "@/types/api";
import { useAppSelector } from "@/store/hooks";

// 僅 admin：OpenRouter Key 管理。明文僅建立時回 last4

type Mode =
  | { kind: "create" }
  | { kind: "edit"; item: OpenRouterKey }
  | null;

export default function OpenRouterKeysPage() {
  const role = useAppSelector((s) => s.auth.actor?.role);
  const { showDialog } = useDialog();
  const { confirm } = useConfirm();

  const [items, setItems] = React.useState<OpenRouterKey[]>([]);
  const [depts, setDepts] = React.useState<Department[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [page, setPage] = React.useState(1);
  const [total, setTotal] = React.useState(0);
  const size = 20;

  const [mode, setMode] = React.useState<Mode>(null);
  const [name, setName] = React.useState("");
  const [departmentUid, setDepartmentUid] = React.useState("");
  const [keyPlain, setKeyPlain] = React.useState("");
  const [rpmLimit, setRpmLimit] = React.useState<string>("0");
  const [minInterval, setMinInterval] = React.useState<string>("0");
  const [saving, setSaving] = React.useState(false);

  const [lastCreated, setLastCreated] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const [list, deptList] = await Promise.all([
        apiClient.get<Paginated<OpenRouterKey>>(API_ENDPOINTS.openrouterKeys, {
          query: { page, size },
        }),
        apiClient.get<Paginated<Department>>(API_ENDPOINTS.departments, {
          query: { page: 1, size: 200 },
        }),
      ]);
      setItems(list.items);
      setTotal(list.total);
      setDepts(deptList.items);
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "載入失敗", message: err.localizedDetail });
      }
    } finally {
      setLoading(false);
    }
  }, [page, showDialog]);

  React.useEffect(() => {
    if (role === "admin") load();
  }, [load, role]);

  if (role !== "admin") {
    return (
      <>
        <PageTitle title="OpenRouter Keys" />
        <Card>
          <CardContent className="pt-6">
            <EmptyState title="權限不足" description="本頁僅限 admin 存取" />
          </CardContent>
        </Card>
      </>
    );
  }

  const deptName = (uid: string) =>
    depts.find((d) => d.department_uid === uid)?.name ?? uid;

  const onOpenCreate = () => {
    setName("");
    setKeyPlain("");
    setDepartmentUid(depts[0]?.department_uid ?? "");
    setRpmLimit("0");
    setMinInterval("0");
    setMode({ kind: "create" });
  };
  const onOpenEdit = (k: OpenRouterKey) => {
    setName(k.name);
    setDepartmentUid(k.department_uid);
    setKeyPlain("");
    setRpmLimit(String(k.rpm_limit));
    setMinInterval(String(k.min_request_interval_ms));
    setMode({ kind: "edit", item: k });
  };

  const onSave = async () => {
    if (mode?.kind === "create") {
      if (!name.trim() || !departmentUid || !keyPlain.trim()) {
        showDialog({
          type: "warning",
          title: "欄位未填",
          message: "請輸入部門、名稱、Key 明文",
        });
        return;
      }
      setSaving(true);
      try {
        const data = await apiClient.post<OpenRouterKey>(
          API_ENDPOINTS.openrouterKeys,
          {
            department_uid: departmentUid,
            name: name.trim(),
            key: keyPlain.trim(),
            rpm_limit: Math.max(0, Number(rpmLimit) || 0),
            min_request_interval_ms: Math.max(0, Number(minInterval) || 0),
          }
        );
        setMode(null);
        setLastCreated(data?.key_last4 ?? "");
        load();
      } catch (err) {
        if (err instanceof ApiError) {
          showDialog({ type: "error", title: "建立失敗", message: err.localizedDetail });
        }
      } finally {
        setSaving(false);
      }
    } else if (mode?.kind === "edit") {
      setSaving(true);
      try {
        await apiClient.patch(
          API_ENDPOINTS.openrouterKeyById(mode.item.openrouter_key_uid),
          {
            name: name.trim(),
            rpm_limit: Math.max(0, Number(rpmLimit) || 0),
            min_request_interval_ms: Math.max(0, Number(minInterval) || 0),
          }
        );
        setMode(null);
        load();
      } catch (err) {
        if (err instanceof ApiError) {
          showDialog({ type: "error", title: "儲存失敗", message: err.localizedDetail });
        }
      } finally {
        setSaving(false);
      }
    }
  };

  const onToggleActive = async (k: OpenRouterKey) => {
    try {
      await apiClient.patch(API_ENDPOINTS.openrouterKeyById(k.openrouter_key_uid), {
        is_active: !k.is_active,
      });
      load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "操作失敗", message: err.localizedDetail });
      }
    }
  };

  const onDelete = async (k: OpenRouterKey) => {
    const ok = await confirm({
      title: "刪除 Key",
      message: (
        <span>
          將軟刪除「<b>{k.name}</b>」（{k.key_prefix}...{k.key_last4}），之後將無法復原，確定嗎？
        </span>
      ),
      destructive: true,
    });
    if (!ok) return;
    try {
      await apiClient.delete(API_ENDPOINTS.openrouterKeyById(k.openrouter_key_uid));
      load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "刪除失敗", message: err.localizedDetail });
      }
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / size));

  return (
    <>
      <PageTitle
        title="OpenRouter Keys"
        description="對外金鑰 · 雲端 — 本平台用來呼叫 OpenRouter API 的金鑰"
        actions={
          <Button onClick={onOpenCreate}>
            <Plus className="h-4 w-4" />
            新增 Key
          </Button>
        }
      />
      <PageHint title="這把 Key 是做什麼用的?">
        <p>
          <strong>方向</strong>:本平台 → OpenRouter(雲端付費 API)。每把 Key 綁
          <strong>部門</strong>;代理呼叫時自該部門的啟用 Key 中隨機挑選,撞速率限制
          自動換下一把(failover)。
        </p>
        <p className="text-muted-foreground text-xs mt-1">
          與「Internal Keys(地端模型)」、「SDK Keys(對內接受 SDK 呼叫)」是不同概念。
          餘額由「模型管理 · 同步」自動更新。
        </p>
      </PageHint>
      <Card>
        <CardContent className="pt-6">
          {loading ? (
            <div className="flex flex-col gap-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <EmptyState title="尚無 OpenRouter Key" />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>部門</TH>
                  <TH>名稱</TH>
                  <TH>Key</TH>
                  <TH>餘額</TH>
                  <TH>速率限制</TH>
                  <TH>狀態</TH>
                  <TH className="text-right">操作</TH>
                </TR>
              </THead>
              <TBody>
                {items.map((k) => (
                  <TR key={k.openrouter_key_uid}>
                    <TD>{deptName(k.department_uid)}</TD>
                    <TD>{k.name}</TD>
                    <TD className="font-mono text-sm whitespace-nowrap">
                      {k.key_prefix}····{k.key_last4}
                    </TD>
                    <TD>
                      <CreditsCell item={k} />
                    </TD>
                    <TD>
                      <RateLimitCell item={k} />
                    </TD>
                    <TD>
                      <button
                        onClick={() => onToggleActive(k)}
                        className="hover:cursor-pointer"
                      >
                        <Badge variant={k.is_active ? "success" : "secondary"}>
                          {k.is_active ? "啟用" : "停用"}
                        </Badge>
                      </button>
                    </TD>
                    <TD className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="編輯"
                          onClick={() => onOpenEdit(k)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="刪除"
                          onClick={() => onDelete(k)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
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

      <Dialog
        open={mode !== null}
        onOpenChange={(o) => !o && setMode(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {mode?.kind === "edit" ? "編輯 Key" : "新增 OpenRouter Key"}
            </DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 pt-4">
            <div className="flex flex-col gap-1.5">
              <Label>所屬部門</Label>
              <select
                className="h-10 w-full rounded-xl border border-border bg-background px-3 text-sm hover:cursor-pointer"
                value={departmentUid}
                onChange={(e) => setDepartmentUid(e.target.value)}
                disabled={mode?.kind === "edit"}
              >
                {depts.map((d) => (
                  <option key={d.department_uid} value={d.department_uid}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>名稱</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            {mode?.kind === "create" && (
              <div className="flex flex-col gap-1.5">
                <Label>Key 明文</Label>
                <Input
                  type="password"
                  value={keyPlain}
                  onChange={(e) => setKeyPlain(e.target.value)}
                  placeholder="sk-or-..."
                />
                <p className="text-sm text-muted-foreground">
                  明文僅存於後端加密欄位；建立完成後僅回末 4 碼。
                </p>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3 border-t border-border pt-3">
              <div className="flex flex-col gap-1.5">
                <Label>每分鐘最大呼叫(RPM)</Label>
                <Input
                  type="number"
                  min={0}
                  value={rpmLimit}
                  onChange={(e) => setRpmLimit(e.target.value)}
                  placeholder="0 = 不限"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>最小請求間隔(ms)</Label>
                <Input
                  type="number"
                  min={0}
                  value={minInterval}
                  onChange={(e) => setMinInterval(e.target.value)}
                  placeholder="0 = 不限"
                />
              </div>
              <p className="col-span-2 text-xs text-muted-foreground leading-relaxed">
                <strong>兩者疊加</strong>:實際等待時間 = max(RPM 視窗剩餘、最小間隔剩餘)。
                <br />
                例:RPM=60、間隔=200ms → 每分鐘 ≤60 次,且任兩次間隔 ≥200ms。
                <br />
                <strong>建議值</strong>:Free Tier 設 20 RPM + 200ms;付費通常設 0(不限),
                讓 OR 自行限流即可。
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setMode(null)}
              disabled={saving}
            >
              取消
            </Button>
            <LoadingButton onClick={onSave} loading={saving}>
              儲存
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={lastCreated !== null}
        onOpenChange={(o) => !o && setLastCreated(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>建立成功</DialogTitle>
          </DialogHeader>
          <div className="pt-4 text-sm">
            Key 已加密儲存，末 4 碼：
            <div className="mt-2 rounded-xl border border-border bg-muted/40 p-3 font-mono break-all">
              ····{lastCreated}
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setLastCreated(null)}>關閉</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function RateLimitCell({ item }: { item: OpenRouterKey }) {
  const rpm = item.rpm_limit > 0 ? `${item.rpm_limit} RPM` : "不限";
  const interval =
    item.min_request_interval_ms > 0 ? `${item.min_request_interval_ms}ms` : "—";
  return (
    <div className="text-sm whitespace-nowrap">
      <div className="font-mono">{rpm}</div>
      <div className="text-xs text-muted-foreground font-mono">間隔 {interval}</div>
    </div>
  );
}

// 餘額顯示:used / limit 進度條 + Free Tier 徽章 + 同步狀態警告
// limit 為 NULL → 顯示「無上限」+ 已用金額,不畫進度條
// credits_synced_at 為 NULL → 顯示「尚未同步」
// credits_synced_at > 24h → 警告色 + tooltip
function CreditsCell({ item }: { item: OpenRouterKey }) {
  const used = item.credits_used_usd != null ? Number(item.credits_used_usd) : null;
  const limit = item.credits_limit_usd != null ? Number(item.credits_limit_usd) : null;
  const synced = item.credits_synced_at ?? null;
  const isFree = item.credits_is_free_tier === true;

  // 同步狀態警告(> 24h 或從未同步)
  const stale = React.useMemo(() => {
    if (!synced) return "never" as const;
    const diffMs = Date.now() - new Date(synced).getTime();
    if (diffMs > 24 * 60 * 60 * 1000) return "stale" as const;
    return "fresh" as const;
  }, [synced]);

  if (used === null && limit === null && synced === null) {
    return (
      <span className="text-sm text-muted-foreground">尚未同步</span>
    );
  }

  // 進度條比例(0-1);limit 為 0 或 NULL 時不畫
  let ratio: number | null = null;
  if (used !== null && limit !== null && limit > 0) {
    ratio = Math.min(1, Math.max(0, used / limit));
  }
  const overEighty = ratio !== null && ratio > 0.8;

  return (
    <div className="flex flex-col gap-1 min-w-[160px]">
      <div className="flex items-center gap-2 text-sm whitespace-nowrap">
        <span className="font-mono">
          ${used !== null ? used.toFixed(2) : "-"}
          {" / "}
          {limit !== null ? `$${limit.toFixed(2)}` : "無上限"}
        </span>
        {isFree && (
          <Badge variant="secondary" className="text-[10px]">
            Free Tier
          </Badge>
        )}
      </div>
      {ratio !== null && (
        <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
          <div
            className={`h-full rounded-full ${
              overEighty ? "bg-destructive" : "bg-primary"
            }`}
            style={{ width: `${ratio * 100}%` }}
          />
        </div>
      )}
      <div
        className={`text-[10px] ${
          stale === "fresh"
            ? "text-muted-foreground"
            : "text-amber-600"
        }`}
        title={
          stale === "stale"
            ? "同步資料過時,請執行模型同步"
            : stale === "never"
            ? "尚未同步,請執行模型同步"
            : undefined
        }
      >
        {synced
          ? `同步於 ${new Date(synced).toLocaleString("zh-TW", {
              hour12: false,
            })}`
          : "尚未同步"}
      </div>
    </div>
  );
}
