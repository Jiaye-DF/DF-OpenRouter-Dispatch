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
import type { Department, Paginated } from "@/types/api";
import { useAppSelector } from "@/store/hooks";

interface FormState {
  department_uid?: string;
  code: string;
  name: string;
  description: string;
}

const EMPTY_FORM: FormState = { code: "", name: "", description: "" };

// 部門頁：列表 + 建立 / 編輯 Dialog + 軟刪除
export default function DepartmentsPage() {
  const isAdmin = useAppSelector((s) => s.auth.actor?.role === "admin");
  const { showDialog } = useDialog();
  const { confirm } = useConfirm();

  const [items, setItems] = React.useState<Department[]>([]);
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
      const data = await apiClient.get<Paginated<Department>>(
        API_ENDPOINTS.departments,
        { query: { page, size } }
      );
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "載入失敗", message: err.detail });
      }
    } finally {
      setLoading(false);
    }
  }, [page, showDialog]);

  React.useEffect(() => {
    load();
  }, [load]);

  const onOpenCreate = () => {
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  };
  const onOpenEdit = (d: Department) => {
    setForm({
      department_uid: d.department_uid,
      code: d.code,
      name: d.name,
      description: d.description ?? "",
    });
    setDialogOpen(true);
  };

  const onSave = async () => {
    if (!form.code.trim() || !form.name.trim()) {
      showDialog({
        type: "warning",
        title: "欄位未填",
        message: "請輸入部門代碼與名稱",
      });
      return;
    }
    setSaving(true);
    try {
      const payload = {
        code: form.code.trim(),
        name: form.name.trim(),
        description: form.description.trim() || null,
      };
      if (form.department_uid) {
        await apiClient.patch(
          API_ENDPOINTS.departmentById(form.department_uid),
          payload
        );
      } else {
        await apiClient.post(API_ENDPOINTS.departments, payload);
      }
      setDialogOpen(false);
      load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "儲存失敗", message: err.detail });
      }
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async (d: Department) => {
    const ok = await confirm({
      title: "刪除部門",
      message: (
        <span>
          將軟刪除「<b>{d.name}</b>」，僅在部門下無啟用的 Key / 專案 / 使用者時才可成功，確定嗎？
        </span>
      ),
      destructive: true,
    });
    if (!ok) return;
    try {
      await apiClient.delete(API_ENDPOINTS.departmentById(d.department_uid));
      load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "刪除失敗", message: err.detail });
      }
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / size));

  return (
    <>
      <PageTitle
        title="部門管理"
        description="部門為 Key 的載體，同一部門可核發多把 OpenRouter / SDK Key"
        actions={
          isAdmin ? (
            <Button onClick={onOpenCreate}>
              <Plus className="h-4 w-4" />
              新增部門
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
            <EmptyState
              title="尚無部門"
              description={
                isAdmin ? "按右上角「新增部門」開始建立" : "請聯絡管理員建立"
              }
            />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>代碼</TH>
                  <TH>名稱</TH>
                  <TH>描述</TH>
                  <TH>狀態</TH>
                  {isAdmin && <TH className="text-right">操作</TH>}
                </TR>
              </THead>
              <TBody>
                {items.map((d) => (
                  <TR key={d.department_uid}>
                    <TD className="font-mono">{d.code}</TD>
                    <TD>{d.name}</TD>
                    <TD className="text-muted-foreground">
                      {d.description ?? "-"}
                    </TD>
                    <TD>
                      <Badge variant={d.is_active ? "success" : "secondary"}>
                        {d.is_active ? "啟用" : "停用"}
                      </Badge>
                    </TD>
                    {isAdmin && (
                      <TD className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="編輯"
                            onClick={() => onOpenEdit(d)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="刪除"
                            onClick={() => onDelete(d)}
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
              {form.department_uid ? "編輯部門" : "新增部門"}
            </DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 pt-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="dept-code">代碼</Label>
              <Input
                id="dept-code"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                placeholder="例：T000"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="dept-name">名稱</Label>
              <Input
                id="dept-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="例：資訊部"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="dept-desc">描述</Label>
              <Input
                id="dept-desc"
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
