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
import { useDialog } from "@/lib/dialog";
import { useConfirm } from "@/components/common/ConfirmDialog";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import type { Department, Paginated, Project } from "@/types/api";
import { useAppSelector } from "@/store/hooks";

interface FormState {
  project_uid?: string;
  department_uid: string;
  code: string;
  name: string;
  description: string;
}

const EMPTY_FORM: FormState = {
  department_uid: "",
  code: "",
  name: "",
  description: "",
};

// 專案頁：列表 + 建立 / 編輯 Dialog（需選部門）
export default function ProjectsPage() {
  const isAdmin = useAppSelector((s) => s.auth.actor?.role === "admin");
  const { showDialog } = useDialog();
  const { confirm } = useConfirm();

  const [items, setItems] = React.useState<Project[]>([]);
  const [depts, setDepts] = React.useState<Department[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [page, setPage] = React.useState(1);
  const [total, setTotal] = React.useState(0);
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [form, setForm] = React.useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = React.useState(false);

  const size = 20;

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const [list, deptList] = await Promise.all([
        apiClient.get<Paginated<Project>>(API_ENDPOINTS.projects, {
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
    load();
  }, [load]);

  const deptName = (uid: string) =>
    depts.find((d) => d.department_uid === uid)?.name ?? uid;

  const onOpenCreate = () => {
    setForm({ ...EMPTY_FORM, department_uid: depts[0]?.department_uid ?? "" });
    setDialogOpen(true);
  };
  const onOpenEdit = (p: Project) => {
    setForm({
      project_uid: p.project_uid,
      department_uid: p.department_uid,
      code: p.code,
      name: p.name,
      description: p.description ?? "",
    });
    setDialogOpen(true);
  };

  const onSave = async () => {
    if (!form.name.trim()) {
      showDialog({
        type: "warning",
        title: "欄位未填",
        message: "請輸入專案名稱",
      });
      return;
    }
    if (!form.project_uid && !form.department_uid) {
      showDialog({
        type: "warning",
        title: "欄位未填",
        message: "請選擇所屬部門",
      });
      return;
    }
    setSaving(true);
    try {
      if (form.project_uid) {
        // 編輯：部門與代碼建立後不可改
        await apiClient.patch(API_ENDPOINTS.projectById(form.project_uid), {
          name: form.name.trim(),
          description: form.description.trim() || null,
        });
      } else {
        // 新增：代碼由後端以 Snowflake ID 自動產生
        await apiClient.post(API_ENDPOINTS.projects, {
          department_uid: form.department_uid,
          name: form.name.trim(),
          description: form.description.trim() || null,
        });
      }
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      setPage(1);
      await load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "儲存失敗", message: err.localizedDetail });
      }
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async (p: Project) => {
    const ok = await confirm({
      title: "刪除專案",
      message: (
        <span>
          將軟刪除「<b>{p.name}</b>」，確定嗎？
        </span>
      ),
      destructive: true,
    });
    if (!ok) return;
    try {
      await apiClient.delete(API_ENDPOINTS.projectById(p.project_uid));
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
        title="專案管理"
        description="專案隸屬於部門，主要用於用量稽核分類"
        actions={
          isAdmin ? (
            <Button onClick={onOpenCreate}>
              <Plus className="h-4 w-4" />
              新增專案
            </Button>
          ) : null
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
            <EmptyState title="尚無專案" />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>部門</TH>
                  <TH>代碼</TH>
                  <TH>名稱</TH>
                  <TH>描述</TH>
                  <TH>狀態</TH>
                  {isAdmin && <TH className="text-right">操作</TH>}
                </TR>
              </THead>
              <TBody>
                {items.map((p) => (
                  <TR key={p.project_uid}>
                    <TD>{deptName(p.department_uid)}</TD>
                    <TD className="font-mono">{p.code}</TD>
                    <TD>{p.name}</TD>
                    <TD className="text-muted-foreground">
                      {p.description ?? "-"}
                    </TD>
                    <TD>
                      <Badge variant={p.is_active ? "success" : "secondary"}>
                        {p.is_active ? "啟用" : "停用"}
                      </Badge>
                    </TD>
                    {isAdmin && (
                      <TD className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="編輯"
                            onClick={() => onOpenEdit(p)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="刪除"
                            onClick={() => onDelete(p)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TD>
                    )}
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

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {form.project_uid ? "編輯專案" : "新增專案"}
            </DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 pt-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="proj-dept">
                所屬部門
                {form.project_uid && (
                  <span className="ml-2 text-xs text-muted-foreground">
                    （建立後不可修改）
                  </span>
                )}
              </Label>
              <select
                id="proj-dept"
                className="h-10 w-full rounded-xl border border-border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 hover:cursor-pointer disabled:cursor-not-allowed disabled:opacity-60"
                value={form.department_uid}
                onChange={(e) =>
                  setForm({ ...form, department_uid: e.target.value })
                }
                disabled={!!form.project_uid}
              >
                {depts.map((d) => (
                  <option key={d.department_uid} value={d.department_uid}>
                    {d.name}（{d.code}）
                  </option>
                ))}
              </select>
            </div>
            {form.project_uid && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="proj-code">
                  代碼
                  <span className="ml-2 text-xs text-muted-foreground">
                    （建立時由系統自動產生，不可修改）
                  </span>
                </Label>
                <Input
                  id="proj-code"
                  value={form.code}
                  placeholder=""
                  disabled
                  readOnly
                />
              </div>
            )}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="proj-name">名稱</Label>
              <Input
                id="proj-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="proj-desc">描述</Label>
              <Input
                id="proj-desc"
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
                placeholder="選填"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDialogOpen(false)}
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
    </>
  );
}
