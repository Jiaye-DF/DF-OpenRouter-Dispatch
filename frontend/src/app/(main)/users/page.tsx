"use client";

import * as React from "react";
import { KeyRound, Plus, ShieldOff, Ticket } from "lucide-react";
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
import type { Department, Paginated, User } from "@/types/api";
import { useAppSelector } from "@/store/hooks";

// 僅 admin 可見：使用者管理（建立 / 重設密碼 / 產生 Token / 撤銷 Token）

interface CreateForm {
  account: string;
  username: string;
  password: string;
  role: "admin" | "user";
  department_uid: string;
  employee_id: string;
  email: string;
}

const EMPTY_CREATE: CreateForm = {
  account: "",
  username: "",
  password: "",
  role: "user",
  department_uid: "",
  employee_id: "",
  email: "",
};

type Mode =
  | { kind: "create" }
  | { kind: "reset"; user: User }
  | { kind: "token"; user: User }
  | null;

export default function UsersPage() {
  const role = useAppSelector((s) => s.auth.actor?.role);
  const { showDialog } = useDialog();
  const { confirm } = useConfirm();

  const [items, setItems] = React.useState<User[]>([]);
  const [depts, setDepts] = React.useState<Department[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [page, setPage] = React.useState(1);
  const [total, setTotal] = React.useState(0);
  const size = 20;

  const [mode, setMode] = React.useState<Mode>(null);
  const [saving, setSaving] = React.useState(false);
  const [createForm, setCreateForm] = React.useState<CreateForm>(EMPTY_CREATE);
  const [resetPwd, setResetPwd] = React.useState("");

  const [revealOpen, setRevealOpen] = React.useState(false);
  const [revealTitle, setRevealTitle] = React.useState("");
  const [revealValue, setRevealValue] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const [users, deptList] = await Promise.all([
        apiClient.get<Paginated<User>>(API_ENDPOINTS.users, {
          query: { page, size },
        }),
        apiClient.get<Paginated<Department>>(API_ENDPOINTS.departments, {
          query: { page: 1, size: 200 },
        }),
      ]);
      setItems(users.items);
      setTotal(users.total);
      setDepts(deptList.items);
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "載入失敗", message: err.detail });
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
        <PageTitle title="使用者管理" />
        <Card>
          <CardContent className="pt-6">
            <EmptyState title="權限不足" description="本頁僅限 admin 存取" />
          </CardContent>
        </Card>
      </>
    );
  }

  const deptName = (uid: string | null) =>
    (uid && depts.find((d) => d.department_uid === uid)?.name) || "-";

  const onCreate = async () => {
    const f = createForm;
    if (f.account.length < 4 || f.username.length < 1 || f.password.length < 10) {
      showDialog({
        type: "warning",
        title: "欄位錯誤",
        message: "帳號 ≥ 4、名稱 ≥ 1、密碼 ≥ 10 字元",
      });
      return;
    }
    setSaving(true);
    try {
      const payload = {
        account: f.account,
        username: f.username,
        password: f.password,
        role: f.role,
        department_uid: f.department_uid || null,
        employee_id: f.employee_id || null,
        email: f.email || null,
      };
      await apiClient.post(API_ENDPOINTS.users, payload);
      setMode(null);
      setCreateForm(EMPTY_CREATE);
      load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "建立失敗", message: err.detail });
      }
    } finally {
      setSaving(false);
    }
  };

  const onReset = async () => {
    if (mode?.kind !== "reset") return;
    if (resetPwd.length < 10) {
      showDialog({
        type: "warning",
        title: "密碼太短",
        message: "新密碼至少 10 字元",
      });
      return;
    }
    setSaving(true);
    try {
      await apiClient.post(
        API_ENDPOINTS.resetUserPassword(mode.user.user_uid),
        { new_password: resetPwd }
      );
      setRevealTitle("新密碼（請立即複製）");
      setRevealValue(resetPwd);
      setRevealOpen(true);
      setMode(null);
      setResetPwd("");
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "重設失敗", message: err.detail });
      }
    } finally {
      setSaving(false);
    }
  };

  const onGenToken = async (user: User) => {
    setSaving(true);
    try {
      const data = await apiClient.post<{ token: string }>(
        API_ENDPOINTS.userTokens(user.user_uid),
        {}
      );
      setRevealTitle(`${user.username} 的 User Token`);
      setRevealValue(data?.token ?? "(後端未回傳 token 欄位)");
      setRevealOpen(true);
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "產生失敗", message: err.detail });
      }
    } finally {
      setSaving(false);
    }
  };

  const onRevokeToken = async (user: User) => {
    const ok = await confirm({
      title: "撤銷 Token",
      message: `將撤銷 ${user.username} 先前核發之所有 User Token，需重新產生。`,
      destructive: true,
      confirmText: "撤銷",
    });
    if (!ok) return;
    try {
      await apiClient.post(
        API_ENDPOINTS.revokeUserTokens(user.user_uid),
        { reason: "admin_revoke" }
      );
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "撤銷失敗", message: err.detail });
      }
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / size));

  return (
    <>
      <PageTitle
        title="使用者管理"
        description="建立使用者、重設密碼、產生或撤銷 User Token"
        actions={
          <Button onClick={() => setMode({ kind: "create" })}>
            <Plus className="h-4 w-4" />
            建立使用者
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
            <EmptyState title="尚無使用者" />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>帳號</TH>
                  <TH>名稱</TH>
                  <TH>角色</TH>
                  <TH>部門</TH>
                  <TH>Email</TH>
                  <TH>狀態</TH>
                  <TH className="text-right">操作</TH>
                </TR>
              </THead>
              <TBody>
                {items.map((u) => (
                  <TR key={u.user_uid}>
                    <TD className="font-mono">{u.account}</TD>
                    <TD>{u.username}</TD>
                    <TD>
                      <Badge variant={u.role === "admin" ? "default" : "secondary"}>
                        {u.role}
                      </Badge>
                    </TD>
                    <TD>{deptName(u.department_uid)}</TD>
                    <TD className="text-muted-foreground">{u.email ?? "-"}</TD>
                    <TD>
                      <Badge variant={u.is_active ? "success" : "secondary"}>
                        {u.is_active ? "啟用" : "停用"}
                      </Badge>
                    </TD>
                    <TD className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="重設密碼"
                          onClick={() => setMode({ kind: "reset", user: u })}
                        >
                          <KeyRound className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="產生 Token"
                          onClick={() => onGenToken(u)}
                        >
                          <Ticket className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="撤銷 Token"
                          onClick={() => onRevokeToken(u)}
                        >
                          <ShieldOff className="h-4 w-4 text-destructive" />
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

      {/* 建立使用者 */}
      <Dialog
        open={mode?.kind === "create"}
        onOpenChange={(o) => !o && setMode(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>建立使用者</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 pt-4">
            <FormField label="帳號（account）">
              <Input
                value={createForm.account}
                onChange={(e) =>
                  setCreateForm({ ...createForm, account: e.target.value })
                }
              />
            </FormField>
            <FormField label="名稱（username）">
              <Input
                value={createForm.username}
                onChange={(e) =>
                  setCreateForm({ ...createForm, username: e.target.value })
                }
              />
            </FormField>
            <FormField label="首次密碼">
              <Input
                type="password"
                value={createForm.password}
                onChange={(e) =>
                  setCreateForm({ ...createForm, password: e.target.value })
                }
              />
            </FormField>
            <div className="grid grid-cols-2 gap-3">
              <FormField label="角色">
                <select
                  value={createForm.role}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      role: e.target.value as "admin" | "user",
                    })
                  }
                  className="h-10 w-full rounded-xl border border-border bg-background px-3 text-sm hover:cursor-pointer"
                >
                  <option value="user">user</option>
                  <option value="admin">admin</option>
                </select>
              </FormField>
              <FormField label="部門">
                <select
                  value={createForm.department_uid}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      department_uid: e.target.value,
                    })
                  }
                  className="h-10 w-full rounded-xl border border-border bg-background px-3 text-sm hover:cursor-pointer"
                >
                  <option value="">（未指定）</option>
                  {depts.map((d) => (
                    <option key={d.department_uid} value={d.department_uid}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </FormField>
            </div>
            <FormField label="員工編號">
              <Input
                value={createForm.employee_id}
                onChange={(e) =>
                  setCreateForm({ ...createForm, employee_id: e.target.value })
                }
                placeholder="選填，SDK Token payload 使用"
              />
            </FormField>
            <FormField label="Email">
              <Input
                value={createForm.email}
                onChange={(e) =>
                  setCreateForm({ ...createForm, email: e.target.value })
                }
                placeholder="選填，SDK Token payload 使用"
              />
            </FormField>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setMode(null)}
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

      {/* 重設密碼 */}
      <Dialog
        open={mode?.kind === "reset"}
        onOpenChange={(o) => !o && setMode(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              重設密碼 · {mode?.kind === "reset" ? mode.user.username : ""}
            </DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 pt-4">
            <FormField label="新密碼（至少 10 字元）">
              <Input
                type="text"
                value={resetPwd}
                onChange={(e) => setResetPwd(e.target.value)}
              />
            </FormField>
            <p className="text-xs text-muted-foreground">
              送出後會顯示明文一次，請以帶外管道交付使用者。
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setMode(null)}
              disabled={saving}
            >
              取消
            </Button>
            <LoadingButton onClick={onReset} loading={saving}>
              重設
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 一次性顯示明文（密碼 / Token） */}
      <Dialog open={revealOpen} onOpenChange={setRevealOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{revealTitle}</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 pt-4">
            <p className="text-sm text-destructive">
              請立即複製，關閉後無法再取得。
            </p>
            <div className="rounded-xl border border-border bg-muted/40 p-3 font-mono text-sm break-all">
              {revealValue}
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                navigator.clipboard.writeText(revealValue).catch(() => {});
              }}
            >
              複製
            </Button>
            <Button onClick={() => setRevealOpen(false)}>關閉</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function FormField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}
