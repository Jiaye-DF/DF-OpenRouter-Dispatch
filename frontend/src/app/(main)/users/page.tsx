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
import { PageHint } from "@/components/common/PageHint";
import { useDialog } from "@/lib/dialog";
import { useConfirm } from "@/components/common/ConfirmDialog";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import type { Department, Paginated, User } from "@/types/api";
import { useAppSelector } from "@/store/hooks";

// 僅 admin 可見：使用者管理
// 一般使用者（role=user）不在平台登入，僅作為 SDK 代理呼叫的身分識別；
// 因此建立時只輸入顯示姓名 / 部門 / 員工編號 / Email；帳號與密碼由後端自動產生。

const EMAIL_SUFFIXES = ["@df-recycle.com", "@df-recycle.com.tw"] as const;
type EmailSuffix = (typeof EMAIL_SUFFIXES)[number];
const EMAIL_LOCAL_RE = /^[A-Za-z0-9._%+-]+$/;

interface CreateForm {
  username: string;
  department_uid: string;
  employee_id: string;
  email: string;
  email_suffix: EmailSuffix;
}

const EMPTY_CREATE: CreateForm = {
  username: "",
  department_uid: "",
  employee_id: "",
  email: "",
  email_suffix: EMAIL_SUFFIXES[0],
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
  const [revealCopied, setRevealCopied] = React.useState(false);

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
    if (!f.username.trim()) {
      showDialog({
        type: "warning",
        title: "欄位未填",
        message: "請輸入姓名",
      });
      return;
    }
    if (!f.department_uid) {
      showDialog({
        type: "warning",
        title: "欄位未填",
        message: "請選擇部門（產生 Token 時必要）",
      });
      return;
    }
    if (!f.employee_id.trim()) {
      showDialog({
        type: "warning",
        title: "欄位未填",
        message: "請輸入員工編號",
      });
      return;
    }
    const emailLocal = f.email.trim();
    if (!emailLocal) {
      showDialog({
        type: "warning",
        title: "欄位未填",
        message: "請輸入 Email 前綴",
      });
      return;
    }
    if (!EMAIL_LOCAL_RE.test(emailLocal)) {
      showDialog({
        type: "warning",
        title: "Email 格式錯誤",
        message: "前綴僅能包含英數字與 . _ % + -",
      });
      return;
    }
    setSaving(true);
    try {
      await apiClient.post(API_ENDPOINTS.users, {
        username: f.username.trim(),
        role: "user",
        department_uid: f.department_uid,
        employee_id: f.employee_id.trim(),
        email: `${emailLocal}${f.email_suffix}`,
      });
      setMode(null);
      setCreateForm(EMPTY_CREATE);
      setPage(1);
      await load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "建立失敗",
          message: err.localizedDetail,
        });
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
      await apiClient.post(API_ENDPOINTS.resetUserPassword(mode.user.user_uid), {
        new_password: resetPwd,
      });
      setRevealTitle("新密碼（請立即複製）");
      setRevealValue(resetPwd);
      setRevealOpen(true);
      setMode(null);
      setResetPwd("");
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "重設失敗",
          message: err.localizedDetail,
        });
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
      setRevealValue(data?.token ?? "");
      setRevealOpen(true);
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "產生失敗",
          message: err.localizedDetail,
        });
      }
    } finally {
      setSaving(false);
    }
  };

  const onRevokeToken = async (user: User) => {
    const ok = await confirm({
      title: `撤銷 ${user.username} 的所有 Token`,
      message: (
        <span>
          將立即作廢 <b>{user.username}</b> 名下所有現存 User Token。
          <br />
          該使用者下次呼叫代理端點會收到 <code className="text-xs">401 unauthorized</code>,
          需重新產生並交付。
          <br />
          <span className="text-muted-foreground text-xs">
            通常用於懷疑外洩或員工離職;若僅是補發新 token,可直接「產生 Token」(舊的不會自動失效,
            如需汰換才需要撤銷)。
          </span>
        </span>
      ),
      destructive: true,
      confirmText: "撤銷全部 Token",
    });
    if (!ok) return;
    try {
      await apiClient.post(API_ENDPOINTS.revokeUserTokens(user.user_uid), {
        reason: "admin_revoke",
      });
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "撤銷失敗",
          message: err.localizedDetail,
        });
      }
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / size));

  return (
    <>
      <PageTitle
        title="使用者管理"
        description="建立 SDK 使用者、產生或撤銷 User Token"
        actions={
          <Button onClick={() => setMode({ kind: "create" })}>
            <Plus className="h-4 w-4" />
            建立使用者
          </Button>
        }
      />
      <PageHint title="User Token 怎麼用?">
        <p>
          User Token 是配合 <strong>SDK Key</strong> 雙因子認證的另一半,代表「
          <strong>哪一位使用者</strong>在呼叫」,呼叫代理端點時放入 <code className="text-xs font-mono">X-User-Token</code> header。
        </p>
        <p className="text-muted-foreground text-xs mt-1">
          <strong>產生</strong>:點列右側 <Ticket className="inline h-3 w-3 mx-0.5" /> 圖示
          → Dialog 一次性顯示明文 → 請<strong>立即複製</strong>並以安全管道交付使用者。
          <strong>撤銷</strong>:點 <ShieldOff className="inline h-3 w-3 mx-0.5 text-destructive" /> 圖示
          → 該使用者名下<strong>所有現存 token 立即失效</strong>(非單張),通常用於外洩處置。
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
            <EmptyState title="尚無使用者" />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>操作</TH>
                  <TH>姓名</TH>
                  <TH>員工編號</TH>
                  <TH>角色</TH>
                  <TH>部門</TH>
                  <TH>Email</TH>
                  <TH>狀態</TH>
                </TR>
              </THead>
              <TBody>
                {items.map((u) => (
                  <TR key={u.user_uid}>
                    <TD>
                      <div className="flex gap-1">
                        {u.role === "admin" && (
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="重設密碼"
                            onClick={() => setMode({ kind: "reset", user: u })}
                          >
                            <KeyRound className="h-4 w-4" />
                          </Button>
                        )}
                        {u.role === "user" && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              title="產生 User Token(一次性顯示)"
                              onClick={() => onGenToken(u)}
                            >
                              <Ticket className="h-4 w-4" />
                              <span className="hidden lg:inline ml-1">產生 Token</span>
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              title="撤銷此使用者所有 Token"
                              onClick={() => onRevokeToken(u)}
                            >
                              <ShieldOff className="h-4 w-4 text-destructive" />
                              <span className="hidden lg:inline ml-1 text-destructive">撤銷全部</span>
                            </Button>
                          </>
                        )}
                      </div>
                    </TD>
                    <TD>{u.username}</TD>
                    <TD className="font-mono text-muted-foreground">
                      {u.employee_id ?? "-"}
                    </TD>
                    <TD>
                      <Badge
                        variant={u.role === "admin" ? "default" : "secondary"}
                      >
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
            <p className="text-sm text-muted-foreground">
              一般使用者僅作為 SDK 呼叫的身分識別,無法登入平台。
            </p>
            <FormField label="姓名">
              <Input
                value={createForm.username}
                onChange={(e) =>
                  setCreateForm({ ...createForm, username: e.target.value })
                }
                placeholder="顯示用姓名"
              />
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
                <option value="">（請選擇）</option>
                {depts.map((d) => (
                  <option key={d.department_uid} value={d.department_uid}>
                    {d.name}（{d.code}）
                  </option>
                ))}
              </select>
            </FormField>
            <FormField label="員工編號">
              <Input
                value={createForm.employee_id}
                onChange={(e) =>
                  setCreateForm({ ...createForm, employee_id: e.target.value })
                }
                placeholder="User Token payload 使用"
              />
            </FormField>
            <FormField label="Email">
              <div className="flex items-stretch rounded-xl border border-border bg-background overflow-hidden focus-within:ring-2 focus-within:ring-ring">
                <input
                  value={createForm.email}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, email: e.target.value })
                  }
                  placeholder="員工帳號前綴"
                  className="h-10 flex-1 min-w-0 bg-transparent px-3 text-sm outline-none"
                />
                <select
                  value={createForm.email_suffix}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      email_suffix: e.target.value as EmailSuffix,
                    })
                  }
                  aria-label="Email 網域"
                  className="h-10 px-3 text-sm text-muted-foreground bg-muted/40 border-l border-border outline-none hover:cursor-pointer focus:text-foreground"
                >
                  {EMAIL_SUFFIXES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
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

      {/* 重設密碼（僅 admin 用戶） */}
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
            <p className="text-sm text-muted-foreground">
              送出後會顯示明文一次,請以帶外管道交付使用者。
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
      <Dialog
        open={revealOpen}
        onOpenChange={(o) => {
          setRevealOpen(o);
          if (!o) setRevealCopied(false);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{revealTitle}</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 pt-4">
            <div className="rounded-xl border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
              ⚠ 明文僅顯示這一次,關閉後無法再取得。請<strong>立即複製</strong>並以
              安全管道(企業內部 IM / 加密 Email)交付使用者。
            </div>
            <div className="rounded-xl border border-border bg-muted/40 p-3 font-mono text-sm break-all">
              {revealValue}
            </div>
            {!revealCopied && (
              <p className="text-xs text-muted-foreground">
                建議先按下「複製明文」確認剪貼簿有內容,再關閉視窗。
              </p>
            )}
          </div>
          <DialogFooter>
            <Button
              variant={revealCopied ? "outline" : "default"}
              onClick={() => {
                navigator.clipboard
                  .writeText(revealValue)
                  .then(() => setRevealCopied(true))
                  .catch(() => {});
              }}
            >
              {revealCopied ? "✓ 已複製,可再複製一次" : "複製明文"}
            </Button>
            <Button
              variant={revealCopied ? "default" : "outline"}
              onClick={() => setRevealOpen(false)}
            >
              {revealCopied ? "完成,關閉" : "關閉(未複製)"}
            </Button>
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
