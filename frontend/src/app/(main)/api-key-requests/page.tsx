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
import { EmptyState } from "@/components/common/EmptyState";
import { useDialog } from "@/lib/dialog";
import { useToast } from "@/components/ui/toaster";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import type { ApiKeyRequest, ApiKeyRequestCreate, Paginated } from "@/types/api";
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

// API Key 申請表單(v1.9):上方送出表單(6 欄全必填)+ 下方歷程列表。
// admin 看全部、member 只看自己(範圍由後端決定,前端不切換查詢)。
export default function ApiKeyRequestsPage() {
  const isAdmin = useAppSelector((s) => s.auth.actor?.role === "admin");
  const { showDialog } = useDialog();
  const { toast } = useToast();

  const [items, setItems] = React.useState<ApiKeyRequest[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [page, setPage] = React.useState(1);
  const [total, setTotal] = React.useState(0);

  const [form, setForm] = React.useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = React.useState(false);

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
      await apiClient.post<ApiKeyRequest>(API_ENDPOINTS.apiKeyRequests, payload);
      toast("申請已送出", "success");
      setForm(EMPTY_FORM);
      setPage(1);
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
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="department_name">部門名稱</Label>
              <Input
                id="department_name"
                value={form.department_name}
                onChange={set("department_name")}
                placeholder="例:資訊部"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="department_code">部門代號</Label>
              <Input
                id="department_code"
                value={form.department_code}
                onChange={set("department_code")}
                placeholder="例:T000"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="project_name">專案名稱</Label>
              <Input
                id="project_name"
                value={form.project_name}
                onChange={set("project_name")}
                placeholder="例:客服機器人"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="project_url">專案連結（GitHub / Replit）</Label>
              <Input
                id="project_url"
                value={form.project_url}
                onChange={set("project_url")}
                placeholder="https://github.com/... 或 https://replit.com/..."
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="owner_name">專案負責人名稱</Label>
              <Input
                id="owner_name"
                value={form.owner_name}
                onChange={set("owner_name")}
                placeholder="例:王小明"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="owner_email">專案負責人信箱</Label>
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
                    <TH>申請時間</TH>
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
                      <TD>
                        <Badge variant="warning">待審核</Badge>
                      </TD>
                      <TD className="whitespace-nowrap text-sm text-muted-foreground">
                        {new Date(it.created_at).toLocaleString()}
                      </TD>
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
    </>
  );
}
