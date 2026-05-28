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
import type { InternalKey, Paginated } from "@/types/api";
import { useAppSelector } from "@/store/hooks";

// 僅 admin:Internal Key 管理(企業內部 OpenAI-compatible server)
// 全平台共用,無 department;每把 Key 可獨立設定速率限制

type Mode =
  | { kind: "create" }
  | { kind: "edit"; item: InternalKey }
  | null;

export default function InternalKeysPage() {
  const role = useAppSelector((s) => s.auth.actor?.role);
  const { showDialog } = useDialog();
  const { confirm } = useConfirm();

  const [items, setItems] = React.useState<InternalKey[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [page, setPage] = React.useState(1);
  const [total, setTotal] = React.useState(0);
  const size = 20;

  const [mode, setMode] = React.useState<Mode>(null);
  const [name, setName] = React.useState("");
  const [baseUrl, setBaseUrl] = React.useState("");
  const [apiKey, setApiKey] = React.useState("");
  const [rpmLimit, setRpmLimit] = React.useState<string>("0");
  const [minInterval, setMinInterval] = React.useState<string>("0");
  const [saving, setSaving] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const list = await apiClient.get<Paginated<InternalKey>>(
        API_ENDPOINTS.internalKeys,
        { query: { page, size } }
      );
      setItems(list.items);
      setTotal(list.total);
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
        <PageTitle title="Internal Keys" />
        <Card>
          <CardContent className="pt-6">
            <EmptyState title="權限不足" description="本頁僅限 admin 存取" />
          </CardContent>
        </Card>
      </>
    );
  }

  const onOpenCreate = () => {
    setName("");
    setBaseUrl("");
    setApiKey("");
    setRpmLimit("0");
    setMinInterval("0");
    setMode({ kind: "create" });
  };
  const onOpenEdit = (k: InternalKey) => {
    setName(k.name);
    setBaseUrl(k.base_url);
    setApiKey(""); // 編輯時不顯示舊 key;留空 = 不動,有值 = 換新
    setRpmLimit(String(k.rpm_limit));
    setMinInterval(String(k.min_request_interval_ms));
    setMode({ kind: "edit", item: k });
  };

  const onSave = async () => {
    if (!name.trim() || !baseUrl.trim()) {
      showDialog({
        type: "warning",
        title: "欄位未填",
        message: "請填入名稱與 Base URL",
      });
      return;
    }
    setSaving(true);
    try {
      if (mode?.kind === "create") {
        await apiClient.post<InternalKey>(API_ENDPOINTS.internalKeys, {
          name: name.trim(),
          base_url: baseUrl.trim(),
          api_key: apiKey || null,
          rpm_limit: Math.max(0, Number(rpmLimit) || 0),
          min_request_interval_ms: Math.max(0, Number(minInterval) || 0),
        });
      } else if (mode?.kind === "edit") {
        const payload: Record<string, unknown> = {
          name: name.trim(),
          base_url: baseUrl.trim(),
          rpm_limit: Math.max(0, Number(rpmLimit) || 0),
          min_request_interval_ms: Math.max(0, Number(minInterval) || 0),
        };
        // 只在使用者輸入新值時才送 api_key(空字串視為「不動」)
        if (apiKey) payload.api_key = apiKey;
        await apiClient.patch(
          API_ENDPOINTS.internalKeyById(mode.item.internal_key_uid),
          payload
        );
      }
      setMode(null);
      load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "儲存失敗", message: err.localizedDetail });
      }
    } finally {
      setSaving(false);
    }
  };

  const onToggleActive = async (k: InternalKey) => {
    try {
      await apiClient.patch(API_ENDPOINTS.internalKeyById(k.internal_key_uid), {
        is_active: !k.is_active,
      });
      load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "操作失敗", message: err.localizedDetail });
      }
    }
  };

  const onDelete = async (k: InternalKey) => {
    const ok = await confirm({
      title: "刪除 Internal Key",
      message: (
        <span>
          將軟刪除「<b>{k.name}</b>」({k.base_url}),確定嗎?
        </span>
      ),
      destructive: true,
    });
    if (!ok) return;
    try {
      await apiClient.delete(API_ENDPOINTS.internalKeyById(k.internal_key_uid));
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
        title="Internal Keys"
        description="對外金鑰 · 地端 — 本平台用來呼叫企業內部 LLM server 的連線設定"
        actions={
          <Button className="whitespace-nowrap" onClick={onOpenCreate}>
            <Plus className="h-4 w-4" />
            新增 Internal Key
          </Button>
        }
      />
      <PageHint title="這把 Key 是做什麼用的?">
        地端 OpenAI-compatible server(vLLM / Ollama 等)的連線設定。
        全平台共用、不綁部門;撞速率會等待至 timeout(地端 server 為稀缺資源)。
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
            <EmptyState
              title="尚無 Internal Key"
              description="按「新增 Internal Key」登記一台地端 server 即可啟用本地模型代理"
            />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>操作</TH>
                  <TH>名稱</TH>
                  <TH>Base URL</TH>
                  <TH>API Key</TH>
                  <TH>速率限制</TH>
                  <TH>狀態</TH>
                </TR>
              </THead>
              <TBody>
                {items.map((k) => (
                  <TR key={k.internal_key_uid}>
                    <TD>
                      <div className="flex gap-1">
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
                    <TD>{k.name}</TD>
                    <TD className="font-mono text-sm break-all">{k.base_url}</TD>
                    <TD className="text-sm">
                      {k.has_api_key ? (
                        <span className="font-mono">····{k.key_last4 ?? ""}</span>
                      ) : (
                        <span className="text-muted-foreground">(無)</span>
                      )}
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

      <Dialog open={mode !== null} onOpenChange={(o) => !o && setMode(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {mode?.kind === "edit" ? "編輯 Internal Key" : "新增 Internal Key"}
            </DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 pt-3">
            <div className="flex flex-col gap-1.5">
              <Label>名稱 *</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="vllm-llama3-prod"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Base URL *</Label>
              <Input
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="http://vllm.corp.local:8000/v1"
              />
              <p className="text-xs text-muted-foreground">
                OpenAI-compatible 路徑;後端會在此 base 後接 `/chat/completions`
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>
                API Key
                {mode?.kind === "edit" && (
                  <span className="ml-2 text-xs text-muted-foreground">
                    (留空 = 不變更)
                  </span>
                )}
              </Label>
              <Input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={
                  mode?.kind === "edit" ? "留空保持原 Key" : "可空(內網信任)"
                }
              />
              <p className="text-xs text-muted-foreground">
                有值即 AES-256-GCM 加密儲存;空值表示 server 不需驗證
              </p>
            </div>

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
                <strong>兩者疊加</strong>:實際等待 = max(RPM 視窗剩餘、最小間隔剩餘)。
                <br />
                例:RPM=30、間隔=0 → 每分鐘 ≤30 次。
                <br />
                <strong>撞限額行為</strong>:Phase 1 自動 failover 換下一把;
                全部 Key 都撞牆才進入 Phase 2 等待(等 `INTERNAL_LLM_RATE_WAIT_TIMEOUT` 秒)。
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMode(null)} disabled={saving}>
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

function RateLimitCell({ item }: { item: InternalKey }) {
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
