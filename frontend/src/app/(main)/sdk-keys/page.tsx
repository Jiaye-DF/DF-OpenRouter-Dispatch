"use client";

import * as React from "react";
import { Plus, Trash2 } from "lucide-react";
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
import { useDialog } from "@/lib/dialog";
import { useConfirm } from "@/components/common/ConfirmDialog";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import type { Department, Paginated, SdkKey } from "@/types/api";
import { useAppSelector } from "@/store/hooks";

// SDK Key 管理頁，明文僅建立時一次性顯示
export default function SdkKeysPage() {
  const role = useAppSelector((s) => s.auth.actor?.role);
  const { showDialog } = useDialog();
  const { confirm } = useConfirm();

  const [items, setItems] = React.useState<SdkKey[]>([]);
  const [depts, setDepts] = React.useState<Department[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [page, setPage] = React.useState(1);
  const [total, setTotal] = React.useState(0);
  const size = 20;

  const [createOpen, setCreateOpen] = React.useState(false);
  const [name, setName] = React.useState("");
  const [departmentUid, setDepartmentUid] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [plain, setPlain] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const [list, deptList] = await Promise.all([
        apiClient.get<Paginated<SdkKey>>(API_ENDPOINTS.sdkKeys, {
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
        <PageTitle title="SDK Keys" />
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

  const onCreate = async () => {
    if (!departmentUid || !name.trim()) {
      showDialog({
        type: "warning",
        title: "欄位未填",
        message: "請選部門並填入名稱",
      });
      return;
    }
    setSaving(true);
    try {
      const data = await apiClient.post<{ key: string }>(API_ENDPOINTS.sdkKeys, {
        department_uid: departmentUid,
        name: name.trim(),
      });
      setCreateOpen(false);
      setName("");
      setDepartmentUid("");
      setPlain(data?.key ?? "(後端未回傳 key 欄位)");
      load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "建立失敗", message: err.localizedDetail });
      }
    } finally {
      setSaving(false);
    }
  };

  const onToggleActive = async (k: SdkKey) => {
    try {
      await apiClient.patch(API_ENDPOINTS.sdkKeyById(k.sdk_api_key_uid), {
        is_active: !k.is_active,
      });
      load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "操作失敗", message: err.localizedDetail });
      }
    }
  };

  const onDelete = async (k: SdkKey) => {
    const ok = await confirm({
      title: "刪除 SDK Key",
      message: `將軟刪除「${k.name}」，確定嗎？`,
      destructive: true,
    });
    if (!ok) return;
    try {
      await apiClient.delete(API_ENDPOINTS.sdkKeyById(k.sdk_api_key_uid));
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
        title="SDK Keys"
        description="SDK 呼叫代理端點時 Header 必帶；明文僅建立時一次性顯示"
        actions={
          <Button
            onClick={() => {
              setDepartmentUid(depts[0]?.department_uid ?? "");
              setCreateOpen(true);
            }}
          >
            <Plus className="h-4 w-4" />
            新增 SDK Key
          </Button>
        }
      />
      <Card>
        <CardContent className="pt-6">
          {loading ? (
            <div className="flex flex-col gap-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <EmptyState title="尚無 SDK Key" />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>部門</TH>
                  <TH>名稱</TH>
                  <TH>Prefix</TH>
                  <TH>狀態</TH>
                  <TH className="text-right">操作</TH>
                </TR>
              </THead>
              <TBody>
                {items.map((k) => (
                  <TR key={k.sdk_api_key_uid}>
                    <TD>{deptName(k.department_uid)}</TD>
                    <TD>{k.name}</TD>
                    <TD className="font-mono text-xs">{k.key_prefix}···</TD>
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
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="刪除"
                        onClick={() => onDelete(k)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
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

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新增 SDK Key</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 pt-4">
            <div className="flex flex-col gap-1.5">
              <Label>所屬部門</Label>
              <select
                className="h-10 w-full rounded-xl border border-border bg-background px-3 text-sm hover:cursor-pointer"
                value={departmentUid}
                onChange={(e) => setDepartmentUid(e.target.value)}
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
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCreateOpen(false)}
              disabled={saving}
            >
              取消
            </Button>
            <LoadingButton onClick={onCreate} loading={saving}>
              建立
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={plain !== null} onOpenChange={(o) => !o && setPlain(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>SDK Key 明文</DialogTitle>
          </DialogHeader>
          <div className="pt-4 flex flex-col gap-2">
            <p className="text-sm text-destructive">
              請立即複製，關閉後無法再取得。
            </p>
            <div className="rounded-xl border border-border bg-muted/40 p-3 font-mono text-sm break-all">
              {plain}
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                if (plain) navigator.clipboard.writeText(plain).catch(() => {});
              }}
            >
              複製
            </Button>
            <Button onClick={() => setPlain(null)}>關閉</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
