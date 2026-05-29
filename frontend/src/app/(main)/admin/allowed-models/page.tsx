"use client";

import * as React from "react";
import { Plus, Trash2 } from "lucide-react";
import { PageTitle } from "@/components/common/PageTitle";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingButton } from "@/components/common/LoadingButton";
import { Input } from "@/components/ui/input";
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
import type { AllowedModel } from "@/types/api";
import { useAppSelector } from "@/store/hooks";

// 模型白名單管理(admin only):編輯後下次 sync 自動生效。
// - is_active=TRUE 的 model_key 才會被 sync 啟用;FALSE 仍保留紀錄(可一鍵重新啟用)
// - 刪除為軟刪除(is_deleted=TRUE),重新新增同 key 會自動還原為 active

interface CreateForm {
  model_key: string;
  note: string;
}

const EMPTY_CREATE: CreateForm = { model_key: "", note: "" };

export default function AllowedModelsPage() {
  const role = useAppSelector((s) => s.auth.actor?.role);
  const { showDialog } = useDialog();
  const { confirm } = useConfirm();

  const [items, setItems] = React.useState<AllowedModel[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [createForm, setCreateForm] = React.useState<CreateForm>(EMPTY_CREATE);
  const [saving, setSaving] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<AllowedModel[]>(
        API_ENDPOINTS.allowedModels
      );
      setItems(data ?? []);
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
  }, [showDialog]);

  React.useEffect(() => {
    if (role === "admin") load();
  }, [load, role]);

  if (role !== "admin") {
    return (
      <>
        <PageTitle title="模型白名單" />
        <Card>
          <CardContent className="pt-6">
            <EmptyState title="權限不足" description="本頁僅限 admin 存取" />
          </CardContent>
        </Card>
      </>
    );
  }

  const onCreate = async () => {
    const key = createForm.model_key.trim();
    if (!key) {
      showDialog({
        type: "warning",
        title: "欄位未填",
        message: "請輸入 model_key",
      });
      return;
    }
    setSaving(true);
    try {
      await apiClient.post(API_ENDPOINTS.allowedModels, {
        model_key: key,
        note: createForm.note.trim() || null,
      });
      setCreateOpen(false);
      setCreateForm(EMPTY_CREATE);
      await load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "新增失敗",
          message: err.localizedDetail,
        });
      }
    } finally {
      setSaving(false);
    }
  };

  const onToggleActive = async (item: AllowedModel) => {
    try {
      await apiClient.patch(API_ENDPOINTS.allowedModelById(item.allowed_model_uid), {
        is_active: !item.is_active,
      });
      await load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "更新失敗",
          message: err.localizedDetail,
        });
      }
    }
  };

  const onDelete = async (item: AllowedModel) => {
    const ok = await confirm({
      title: `刪除白名單 · ${item.model_key}`,
      message: (
        <span>
          刪除後此 model_key 將從白名單移除,<strong>下次 sync</strong> 對應的
          model.is_active 會被覆寫為 FALSE,SDK user 無法再呼叫。
          <br />
          <span className="text-muted-foreground text-sm">
            若只是暫時停用,建議改按「停用」(可一鍵還原)。重新新增同 key 會還原成 active。
          </span>
        </span>
      ),
      destructive: true,
      confirmText: "刪除",
    });
    if (!ok) return;
    try {
      await apiClient.delete(API_ENDPOINTS.allowedModelById(item.allowed_model_uid));
      await load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "刪除失敗",
          message: err.localizedDetail,
        });
      }
    }
  };

  return (
    <>
      <PageTitle
        title="模型白名單"
        description="編輯後下次 sync 自動套用;白名單以外的 OpenRouter 模型一律停用"
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            新增模型
          </Button>
        }
      />
      <PageHint title="運作邏輯">
        每次 sync 強制套用本表:<code className="text-sm">is_active=TRUE</code> 的 model_key →
        對應 <code className="text-sm">models.is_active=TRUE</code>;表內沒有 / 已停用的 → 一律停用,
        SDK user 呼叫會收到 <code className="text-sm">403 model_forbidden</code>。
      </PageHint>
      <Card>
        <CardContent className="pt-6">
          {loading ? (
            <div className="flex flex-col gap-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <EmptyState
              title="尚無白名單"
              description="新增任一 OpenRouter model_key(例:google/gemini-2.5-flash)"
            />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>狀態</TH>
                  <TH>model_key</TH>
                  <TH>備註</TH>
                  <TH className="text-right">操作</TH>
                </TR>
              </THead>
              <TBody>
                {items.map((it) => (
                  <TR key={it.allowed_model_uid}>
                    <TD>
                      <Badge variant={it.is_active ? "success" : "secondary"}>
                        {it.is_active ? "啟用" : "停用"}
                      </Badge>
                    </TD>
                    <TD className="font-mono text-sm">{it.model_key}</TD>
                    <TD className="text-muted-foreground text-sm">
                      {it.note ?? "-"}
                    </TD>
                    <TD className="text-right">
                      <div className="flex gap-2 justify-end">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onToggleActive(it)}
                        >
                          {it.is_active ? "停用" : "啟用"}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="刪除"
                          onClick={() => onDelete(it)}
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

      <Dialog
        open={createOpen}
        onOpenChange={(o) => {
          if (!o) {
            setCreateOpen(false);
            setCreateForm(EMPTY_CREATE);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新增白名單模型</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 pt-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">model_key</label>
              <Input
                value={createForm.model_key}
                onChange={(e) =>
                  setCreateForm({ ...createForm, model_key: e.target.value })
                }
                placeholder="例:google/gemini-2.5-flash"
                className="font-mono"
              />
              <p className="text-sm text-muted-foreground">
                必須完全符合 OpenRouter 的 model_key 字串。下次 sync 時才會生效。
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">備註(選填)</label>
              <Input
                value={createForm.note}
                onChange={(e) =>
                  setCreateForm({ ...createForm, note: e.target.value })
                }
                placeholder="例:預設 / 低成本備援 / 高階推理"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setCreateOpen(false);
                setCreateForm(EMPTY_CREATE);
              }}
              disabled={saving}
            >
              取消
            </Button>
            <LoadingButton onClick={onCreate} loading={saving}>
              新增
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
