"use client";

import * as React from "react";
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
import { useToast } from "@/components/ui/toaster";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import type {
  ApiKeyRequest,
  ApiKeyRequestCreate,
  ApiKeyRequestDetail,
  Paginated,
  ProvisionedSecrets,
  ResendNotifyResult,
} from "@/types/api";
import { useAppSelector } from "@/store/hooks";

interface FormState {
  department_name: string;
  department_code: string;
  project_name: string;
  project_url: string;
  owner_name: string;
  owner_email: string;
}

const EMPTY_FORM: FormState = {
  department_name: "",
  department_code: "",
  project_name: "",
  project_url: "",
  owner_name: "",
  owner_email: "",
};

// 狀態 badge 對應(v1.9.1 狀態模型)
function statusBadge(status: string): React.ReactElement {
  switch (status) {
    case "manual_pending":
      return <Badge variant="warning">待人工處理</Badge>;
    case "agent_done":
      return <Badge variant="success">Agent 已處理</Badge>;
    case "done":
      return <Badge variant="success">已處理</Badge>;
    case "revoked":
      return <Badge variant="secondary">已撤銷</Badge>;
    case "cancelled":
      return <Badge variant="secondary">已取消</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

// v1.9.2 通知失敗原因碼 → 中文(僅作狀態顯示;未列出者原樣顯示代碼)
const NOTIFY_ERROR_LABELS: Record<string, string> = {
  m365_not_configured: "M365 寄信未設定",
  m365_sendmail_502: "寄信服務暫時不可用",
};

function notifyErrorLabel(code: string): string {
  return NOTIFY_ERROR_LABELS[code] ?? code;
}

// v1.9.2 開通完成 Email 通知狀態(已通知 / 通知失敗 / 尚未通知)
function NotifyStatus({ it }: { it: ApiKeyRequest }): React.ReactElement {
  // 僅開通終態才有通知意義
  if (it.status !== "agent_done" && it.status !== "done") {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  if (it.notified_at) {
    return (
      <div className="flex flex-col">
        <Badge variant="success">已通知</Badge>
        <span className="mt-0.5 text-xs text-muted-foreground">
          {new Date(it.notified_at).toLocaleString()}
        </span>
      </div>
    );
  }
  if (it.notify_error) {
    return (
      <div className="flex flex-col">
        <Badge variant="warning">通知失敗</Badge>
        <span className="mt-0.5 text-xs text-muted-foreground">
          {notifyErrorLabel(it.notify_error)}
        </span>
      </div>
    );
  }
  return <span className="text-xs text-muted-foreground">尚未通知</span>;
}

// 專案連結:須為 GitHub / Replit(前端即時提示,真正把關在後端)
function isGithubOrReplit(url: string): boolean {
  try {
    const u = new URL(url.trim());
    if (u.protocol !== "http:" && u.protocol !== "https:") return false;
    const host = u.hostname.toLowerCase();
    return (
      host === "github.com" ||
      host === "www.github.com" ||
      host === "replit.com" ||
      host === "replit.dev" ||
      host.endsWith(".github.com") ||
      host.endsWith(".replit.com") ||
      host.endsWith(".replit.dev")
    );
  } catch {
    return false;
  }
}

// 必填欄位標籤:標題後加紅色 * 標記
function ReqLabel({
  htmlFor,
  children,
}: {
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <Label htmlFor={htmlFor}>
      {children}
      <span className="ml-0.5 text-destructive">*</span>
    </Label>
  );
}

// API Key 申請表單(v1.9 / v1.9.1):上方送出表單(6 欄全必填)+ 下方歷程列表與生命週期操作。
// admin 看全部、member 只看自己(範圍由後端決定,前端不切換查詢)。
export default function ApiKeyRequestsPage() {
  const actor = useAppSelector((s) => s.auth.actor);
  const isAdmin = actor?.role === "admin";
  const currentUserUid = actor?.user_uid ?? null;
  const { showDialog } = useDialog();
  const { toast } = useToast();

  const [items, setItems] = React.useState<ApiKeyRequest[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [page, setPage] = React.useState(1);
  const [total, setTotal] = React.useState(0);

  const [form, setForm] = React.useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = React.useState(false);

  // 列操作 pending 狀態(以 request_uid 標記,避免重複點擊)
  const [actingUid, setActingUid] = React.useState<string | null>(null);

  // 一次性憑證視窗
  const [secrets, setSecrets] = React.useState<ProvisionedSecrets | null>(null);

  // 取消原因輸入視窗(受控,最小可用版)
  const [cancelTarget, setCancelTarget] = React.useState<ApiKeyRequest | null>(
    null
  );
  const [cancelReason, setCancelReason] = React.useState("");
  const [cancelSaving, setCancelSaving] = React.useState(false);

  // 人工處理視窗(admin):顯示 agent_decision 後確認開通
  const [processTarget, setProcessTarget] =
    React.useState<ApiKeyRequestDetail | null>(null);
  const [processSaving, setProcessSaving] = React.useState(false);

  const size = 20;
  const totalPages = Math.max(1, Math.ceil(total / size));

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const resp = await apiClient.get<Paginated<ApiKeyRequest>>(
        API_ENDPOINTS.apiKeyRequests,
        { query: { page, size } }
      );
      setItems(resp.items);
      setTotal(resp.total);
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

  // 顯示一次性憑證視窗(sdk_key 為 null 時提示向管理員索取)
  const showSecrets = React.useCallback((s: ProvisionedSecrets) => {
    setSecrets(s);
  }, []);

  const onSubmit = async () => {
    const f: FormState = {
      department_name: form.department_name.trim(),
      department_code: form.department_code.trim(),
      project_name: form.project_name.trim(),
      project_url: form.project_url.trim(),
      owner_name: form.owner_name.trim(),
      owner_email: form.owner_email.trim(),
    };
    // 全欄必填
    if (Object.values(f).some((v) => !v)) {
      showDialog({ type: "warning", title: "欄位未填", message: "請填寫所有必填欄位" });
      return;
    }
    if (!isGithubOrReplit(f.project_url)) {
      showDialog({
        type: "warning",
        title: "專案連結格式不符",
        message: "專案連結須為 GitHub 或 Replit 連結",
      });
      return;
    }
    setSaving(true);
    try {
      const payload: ApiKeyRequestCreate = f;
      const detail = await apiClient.post<ApiKeyRequestDetail>(
        API_ENDPOINTS.apiKeyRequests,
        payload
      );
      toast("申請已送出", "success");
      setForm(EMPTY_FORM);
      setPage(1);
      // 自動開通成功 → 彈一次性憑證視窗
      if (detail.status === "agent_done" && detail.provisioned_secrets) {
        showSecrets(detail.provisioned_secrets);
      }
      await load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "送出失敗", message: err.localizedDetail });
      }
    } finally {
      setSaving(false);
    }
  };

  const set = (k: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [k]: e.target.value }));

  // 撤銷(二次確認)
  const onRevoke = (it: ApiKeyRequest) => {
    showDialog({
      type: "warning",
      title: "確認撤銷申請",
      message: "撤銷後此申請將標記為已撤銷且無法復原,確定撤銷?",
      confirmText: "確定撤銷",
      destructive: true,
      onConfirm: async () => {
        setActingUid(it.request_uid);
        try {
          await apiClient.post(
            API_ENDPOINTS.revokeApiKeyRequest(it.request_uid)
          );
          toast("已撤銷申請", "success");
          await load();
        } catch (err) {
          if (err instanceof ApiError) {
            showDialog({
              type: "error",
              title: "撤銷失敗",
              message: err.localizedDetail,
            });
          }
        } finally {
          setActingUid(null);
        }
      },
    });
  };

  // 取消(填原因)→ 開啟受控輸入視窗
  const openCancel = (it: ApiKeyRequest) => {
    setCancelReason("");
    setCancelTarget(it);
  };

  const submitCancel = async () => {
    if (!cancelTarget) return;
    const reason = cancelReason.trim();
    if (!reason) {
      showDialog({ type: "warning", title: "請填寫取消原因" });
      return;
    }
    setCancelSaving(true);
    try {
      await apiClient.post(
        API_ENDPOINTS.cancelApiKeyRequest(cancelTarget.request_uid),
        { reason }
      );
      toast("已取消申請", "success");
      setCancelTarget(null);
      await load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "取消失敗",
          message: err.localizedDetail,
        });
      }
    } finally {
      setCancelSaving(false);
    }
  };

  // 領取一次性憑證(本人)
  const onClaim = async (it: ApiKeyRequest) => {
    setActingUid(it.request_uid);
    try {
      const s = await apiClient.post<ProvisionedSecrets | null>(
        API_ENDPOINTS.claimApiKeyRequestSecrets(it.request_uid)
      );
      if (
        s &&
        (s.sdk_key != null || s.user_token != null || s.project_code != null)
      ) {
        showSecrets(s);
      } else {
        showDialog({
          type: "info",
          title: "無可領取的憑證",
          message: "此申請的一次性憑證已被領取或無內容。",
        });
      }
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "領取失敗",
          message: err.localizedDetail,
        });
      }
    } finally {
      setActingUid(null);
    }
  };

  // admin:人工處理 → 先取詳情顯示 agent_decision,確認後開通
  const openProcess = async (it: ApiKeyRequest) => {
    setActingUid(it.request_uid);
    try {
      const detail = await apiClient.get<ApiKeyRequestDetail>(
        API_ENDPOINTS.apiKeyRequestById(it.request_uid)
      );
      setProcessTarget(detail);
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "載入詳情失敗",
          message: err.localizedDetail,
        });
      }
    } finally {
      setActingUid(null);
    }
  };

  const submitProcess = async () => {
    if (!processTarget) return;
    setProcessSaving(true);
    try {
      const detail = await apiClient.post<ApiKeyRequestDetail>(
        API_ENDPOINTS.processApiKeyRequest(processTarget.request_uid)
      );
      toast("已完成人工處理", "success");
      setProcessTarget(null);
      if (detail.provisioned_secrets) {
        showSecrets(detail.provisioned_secrets);
      }
      await load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "處理失敗",
          message: err.localizedDetail,
        });
      }
    } finally {
      setProcessSaving(false);
    }
  };

  // admin:重送開通完成 Email 通知(二次確認)
  const onResendNotify = (it: ApiKeyRequest) => {
    showDialog({
      type: "warning",
      title: "確認重送通知",
      message: `將重新寄送開通憑證 Email 給 ${it.owner_email},確定重送?`,
      confirmText: "確定重送",
      onConfirm: async () => {
        setActingUid(it.request_uid);
        try {
          const res = await apiClient.post<ResendNotifyResult>(
            API_ENDPOINTS.resendApiKeyRequestNotify(it.request_uid)
          );
          if (res.notified_at) {
            toast("已重送通知", "success");
          } else {
            // 後端 best-effort:HTTP 2xx 但寄送失敗,以 notify_error 提示
            showDialog({
              type: "warning",
              title: "通知寄送失敗",
              message: res.notify_error
                ? `寄送失敗:${notifyErrorLabel(res.notify_error)}`
                : "寄送失敗,請稍後再試。",
            });
          }
          await load();
        } catch (err) {
          if (err instanceof ApiError) {
            showDialog({
              type: "error",
              title: "重送失敗",
              message: err.localizedDetail,
            });
          }
        } finally {
          setActingUid(null);
        }
      },
    });
  };

  // 依列與身分推導可用操作
  const renderActions = (it: ApiKeyRequest): React.ReactNode => {
    const isOwner = currentUserUid != null && it.applicant_user_uid === currentUserUid;
    const busy = actingUid === it.request_uid;
    const actions: React.ReactNode[] = [];

    if (isOwner) {
      if (it.status === "manual_pending") {
        actions.push(
          <Button
            key="cancel"
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={() => openCancel(it)}
          >
            取消
          </Button>,
          <LoadingButton
            key="revoke"
            variant="destructive"
            size="sm"
            loading={busy}
            onClick={() => onRevoke(it)}
          >
            撤銷
          </LoadingButton>
        );
      } else if (it.status === "agent_done" || it.status === "done") {
        actions.push(
          <LoadingButton
            key="claim"
            variant="outline"
            size="sm"
            loading={busy}
            onClick={() => onClaim(it)}
          >
            領取憑證
          </LoadingButton>
        );
      }
    }

    if (isAdmin && it.status === "manual_pending") {
      actions.push(
        <LoadingButton
          key="process"
          size="sm"
          loading={busy}
          onClick={() => openProcess(it)}
        >
          人工處理
        </LoadingButton>
      );
    }

    // v1.9.2 admin:已開通但通知失敗 / 尚未通知 → 可重送通知
    if (
      isAdmin &&
      (it.status === "agent_done" || it.status === "done") &&
      !it.notified_at
    ) {
      actions.push(
        <LoadingButton
          key="resend-notify"
          variant="outline"
          size="sm"
          loading={busy}
          onClick={() => onResendNotify(it)}
        >
          重送通知
        </LoadingButton>
      );
    }

    if (actions.length === 0) {
      return <span className="text-xs text-muted-foreground">—</span>;
    }
    return <div className="flex flex-wrap gap-2">{actions}</div>;
  };

  return (
    <>
      <PageTitle
        title="API Key 申請表單"
        description={
          isAdmin
            ? "送出申請,並檢視所有使用者送出的申請紀錄。"
            : "填寫並送出 API Key 申請,下方為你送出的歷程紀錄。"
        }
      />

      <Card className="mb-6">
        <CardContent className="pt-6">
          <p className="mb-4 text-sm text-muted-foreground">
            以下欄位<span className="text-destructive">皆為必填</span>(標
            <span className="text-destructive">*</span>)。
          </p>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <ReqLabel htmlFor="department_name">部門名稱</ReqLabel>
              <Input
                id="department_name"
                value={form.department_name}
                onChange={set("department_name")}
                placeholder="例:資訊部"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <ReqLabel htmlFor="department_code">部門代號</ReqLabel>
              <Input
                id="department_code"
                value={form.department_code}
                onChange={set("department_code")}
                placeholder="例:T000"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <ReqLabel htmlFor="project_name">專案名稱</ReqLabel>
              <Input
                id="project_name"
                value={form.project_name}
                onChange={set("project_name")}
                placeholder="例:客服機器人"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <ReqLabel htmlFor="project_url">專案連結（GitHub / Replit）</ReqLabel>
              <Input
                id="project_url"
                value={form.project_url}
                onChange={set("project_url")}
                placeholder="https://github.com/... 或 https://replit.com/..."
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <ReqLabel htmlFor="owner_name">專案負責人名稱</ReqLabel>
              <Input
                id="owner_name"
                value={form.owner_name}
                onChange={set("owner_name")}
                placeholder="例:王小明"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <ReqLabel htmlFor="owner_email">專案負責人信箱</ReqLabel>
              <Input
                id="owner_email"
                type="email"
                value={form.owner_email}
                onChange={set("owner_email")}
                placeholder="例:ming@df-recycle.com.tw"
              />
            </div>
          </div>
          <div className="mt-4 flex justify-end">
            <LoadingButton onClick={onSubmit} loading={saving}>
              送出申請
            </LoadingButton>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          {loading ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : items.length === 0 ? (
            <EmptyState
              title="尚無申請紀錄"
              description={isAdmin ? "目前沒有任何申請單。" : "你尚未送出任何申請。"}
            />
          ) : (
            <>
              <Table>
                <THead>
                  <TR>
                    <TH>部門名稱</TH>
                    <TH>部門代號</TH>
                    <TH>專案名稱</TH>
                    <TH>專案連結</TH>
                    <TH>負責人</TH>
                    <TH>狀態</TH>
                    <TH>通知</TH>
                    <TH>申請時間</TH>
                    <TH>操作</TH>
                  </TR>
                </THead>
                <TBody>
                  {items.map((it) => (
                    <TR key={it.request_uid}>
                      <TD>{it.department_name}</TD>
                      <TD className="font-mono">{it.department_code}</TD>
                      <TD>{it.project_name}</TD>
                      <TD className="max-w-[220px] truncate">
                        <a
                          href={it.project_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-primary underline-offset-2 hover:underline"
                        >
                          {it.project_url}
                        </a>
                      </TD>
                      <TD>
                        <div className="flex flex-col">
                          <span>{it.owner_name}</span>
                          <span className="text-xs text-muted-foreground">
                            {it.owner_email}
                          </span>
                        </div>
                      </TD>
                      <TD>{statusBadge(it.status)}</TD>
                      <TD className="whitespace-nowrap">
                        <NotifyStatus it={it} />
                      </TD>
                      <TD className="whitespace-nowrap text-sm text-muted-foreground">
                        {new Date(it.created_at).toLocaleString()}
                      </TD>
                      <TD>{renderActions(it)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>

              <div className="mt-4 flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
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
            </>
          )}
        </CardContent>
      </Card>

      {/* 取消原因輸入視窗(受控最小版) */}
      <Dialog
        open={cancelTarget !== null}
        onOpenChange={(o) => {
          if (!o && !cancelSaving) setCancelTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>取消申請</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-1.5 pt-2">
            <ReqLabel htmlFor="cancel_reason">取消原因</ReqLabel>
            <Input
              id="cancel_reason"
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder="請說明取消原因"
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setCancelTarget(null)}
              disabled={cancelSaving}
            >
              關閉
            </Button>
            <LoadingButton loading={cancelSaving} onClick={submitCancel}>
              確定取消
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* admin 人工處理視窗:顯示 agent_decision */}
      <Dialog
        open={processTarget !== null}
        onOpenChange={(o) => {
          if (!o && !processSaving) setProcessTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>人工處理申請</DialogTitle>
          </DialogHeader>
          {processTarget && (
            <div className="flex flex-col gap-3 pt-2 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-muted-foreground">專案</span>
                <span>
                  {processTarget.department_name}（
                  {processTarget.department_code}） / {processTarget.project_name}
                </span>
              </div>
              {processTarget.agent_decision ? (
                <div className="rounded-lg border border-border bg-muted/40 p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">AI 信心分數</span>
                    <span className="font-mono font-semibold">
                      {processTarget.agent_decision.confidence}
                    </span>
                  </div>
                  <p className="mt-2 text-foreground/80 leading-relaxed">
                    {processTarget.agent_decision.reason || "（無理由）"}
                  </p>
                  {processTarget.agent_decision.error && (
                    <p className="mt-2 text-destructive">
                      AI 錯誤:{processTarget.agent_decision.error}
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-muted-foreground">此申請無 AI 決策紀錄。</p>
              )}
              {processTarget.error_message && (
                <p className="text-destructive">
                  錯誤訊息:{processTarget.error_message}
                </p>
              )}
              <p className="text-muted-foreground">
                確認後將以確定性流程開通並標記為「已處理」。
              </p>
            </div>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setProcessTarget(null)}
              disabled={processSaving}
            >
              關閉
            </Button>
            <LoadingButton loading={processSaving} onClick={submitProcess}>
              確認開通
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 一次性憑證視窗 */}
      <Dialog
        open={secrets !== null}
        onOpenChange={(o) => {
          if (!o) setSecrets(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>一次性憑證</DialogTitle>
          </DialogHeader>
          {secrets && (
            <div className="flex flex-col gap-3 pt-2 text-sm">
              <p className="text-muted-foreground">
                以下憑證僅顯示一次,請立即妥善保存。
              </p>
              <div className="flex flex-col gap-1">
                <span className="text-muted-foreground">SDK Key</span>
                {secrets.sdk_key ? (
                  <code className="break-all rounded-md bg-muted px-2 py-1 font-mono">
                    {secrets.sdk_key}
                  </code>
                ) : (
                  <span className="text-amber-600">請向管理員索取</span>
                )}
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-muted-foreground">User Token</span>
                <code className="break-all rounded-md bg-muted px-2 py-1 font-mono">
                  {secrets.user_token ?? "—"}
                </code>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-muted-foreground">Project Code</span>
                <code className="break-all rounded-md bg-muted px-2 py-1 font-mono">
                  {secrets.project_code ?? "—"}
                </code>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button type="button" onClick={() => setSecrets(null)}>
              我已保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
