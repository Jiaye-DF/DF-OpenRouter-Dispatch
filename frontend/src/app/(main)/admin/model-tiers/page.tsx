"use client";

import * as React from "react";
import Link from "next/link";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { PageTitle } from "@/components/common/PageTitle";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingButton } from "@/components/common/LoadingButton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  ModelTier,
  ModelTierCreate,
  ModelTierPatch,
  TierInUseData,
} from "@/types/api";
import { useAppSelector } from "@/store/hooks";

// 後端儲存單位為 USD/token;前端輸入是 USD/M tok,送出時除以 1_000_000;顯示時乘回
function tokenToMtokInput(perToken: string | null | undefined): string {
  if (perToken === null || perToken === undefined || perToken === "") return "";
  const n = Number(perToken);
  if (!Number.isFinite(n)) return "";
  // 乘回 1_000_000 並去掉尾隨 0
  const mtok = n * 1_000_000;
  return mtok.toString();
}

function mtokInputToToken(mtok: string): string | null {
  const trimmed = mtok.trim();
  if (trimmed === "") return null;
  const n = Number(trimmed);
  if (!Number.isFinite(n)) return null;
  // 12 位小數對齊 NUMERIC(20, 12)
  return (n / 1_000_000).toFixed(12);
}

interface FormState {
  key: string;
  label_zh: string;
  label_en: string;
  color: string;
  sort_order: string;
  auto_min: string; // USD/M tok
  auto_max: string; // USD/M tok
}

const EMPTY_FORM: FormState = {
  key: "",
  label_zh: "",
  label_en: "",
  color: "",
  sort_order: "0",
  auto_min: "",
  auto_max: "",
};

type Mode =
  | { kind: "create" }
  | { kind: "edit"; item: ModelTier }
  | null;

// 顏色字串 → CSS color(支援 hex 與 Tailwind palette 名)
const tailwindColor: Record<string, string> = {
  gray: "#9ca3af",
  green: "#10b981",
  blue: "#3b82f6",
  orange: "#f97316",
  red: "#ef4444",
  purple: "#a855f7",
  yellow: "#eab308",
};

function resolveColor(c: string | null | undefined): string {
  if (!c) return "";
  const isHex = /^#?[0-9a-fA-F]{3,8}$/.test(c);
  if (isHex) return c.startsWith("#") ? c : `#${c}`;
  return tailwindColor[c] ?? "";
}

export default function ModelTiersPage() {
  const role = useAppSelector((s) => s.auth.actor?.role);
  const { showDialog } = useDialog();
  const { toast } = useToast();

  const [items, setItems] = React.useState<ModelTier[]>([]);
  const [loading, setLoading] = React.useState(true);

  const [mode, setMode] = React.useState<Mode>(null);
  const [form, setForm] = React.useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = React.useState(false);

  // tier_in_use 錯誤的內嵌訊息(留在 confirm 流程中顯示)
  const [deleteTarget, setDeleteTarget] = React.useState<ModelTier | null>(null);
  const [tierInUse, setTierInUse] = React.useState<string[] | null>(null);
  const [deleting, setDeleting] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const list = await apiClient.get<ModelTier[]>(API_ENDPOINTS.modelTiers);
      setItems(list);
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
        <PageTitle title="模型分級" />
        <Card>
          <CardContent className="pt-6">
            <EmptyState title="權限不足" description="本頁僅限 admin 存取" />
          </CardContent>
        </Card>
      </>
    );
  }

  const onOpenCreate = () => {
    setForm(EMPTY_FORM);
    setMode({ kind: "create" });
  };
  const onOpenEdit = (t: ModelTier) => {
    setForm({
      key: t.key,
      label_zh: t.label_zh,
      label_en: t.label_en ?? "",
      color: t.color ?? "",
      sort_order: String(t.sort_order ?? 0),
      auto_min: tokenToMtokInput(t.auto_match_min_price_per_mtok),
      auto_max: tokenToMtokInput(t.auto_match_max_price_per_mtok),
    });
    setMode({ kind: "edit", item: t });
  };

  const onSave = async () => {
    if (!form.label_zh.trim()) {
      showDialog({
        type: "warning",
        title: "欄位未填",
        message: "中文名稱為必填",
      });
      return;
    }
    if (mode?.kind === "create" && !form.key.trim()) {
      showDialog({
        type: "warning",
        title: "欄位未填",
        message: "Key 為必填(建立後不可改)",
      });
      return;
    }
    setSaving(true);
    try {
      const sortOrder = Number(form.sort_order);
      const minToken = mtokInputToToken(form.auto_min);
      const maxToken = mtokInputToToken(form.auto_max);
      if (mode?.kind === "create") {
        const body: ModelTierCreate = {
          key: form.key.trim(),
          label_zh: form.label_zh.trim(),
          label_en: form.label_en.trim() || null,
          color: form.color.trim() || null,
          sort_order: Number.isFinite(sortOrder) ? sortOrder : 0,
          auto_match_min_price_per_mtok: minToken,
          auto_match_max_price_per_mtok: maxToken,
        };
        await apiClient.post(API_ENDPOINTS.modelTiers, body);
        toast("分級已建立", "success");
      } else if (mode?.kind === "edit") {
        const body: ModelTierPatch = {
          label_zh: form.label_zh.trim(),
          label_en: form.label_en.trim() || null,
          color: form.color.trim() || null,
          sort_order: Number.isFinite(sortOrder) ? sortOrder : 0,
          auto_match_min_price_per_mtok: minToken,
          auto_match_max_price_per_mtok: maxToken,
        };
        await apiClient.patch(
          API_ENDPOINTS.modelTierById(mode.item.tier_uid),
          body
        );
        toast("分級已更新", "success");
      }
      setMode(null);
      await load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "儲存失敗",
          message: err.localizedDetail,
        });
      }
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setTierInUse(null);
    try {
      await apiClient.delete(API_ENDPOINTS.modelTierById(deleteTarget.tier_uid));
      toast("分級已刪除", "success");
      setDeleteTarget(null);
      await load();
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.detail === "tier_in_use") {
          const payload = err.data as TierInUseData | null;
          setTierInUse(payload?.using_models ?? []);
        } else {
          showDialog({
            type: "error",
            title: "刪除失敗",
            message: err.localizedDetail,
          });
          setDeleteTarget(null);
        }
      }
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <PageTitle
        title="模型分級"
        description="同步時依價格自動匹配;Key 建立後不可改"
        actions={
          <Button onClick={onOpenCreate}>
            <Plus className="h-4 w-4" />
            新增分級
          </Button>
        }
      />
      <Card>
        <CardContent className="pt-6">
          {loading ? (
            <div className="flex flex-col gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <EmptyState
              title="尚無分級"
              description="點右上角「新增分級」建立第一筆"
            />
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>中文名稱</TH>
                  <TH>英文名稱</TH>
                  <TH>Key</TH>
                  <TH>顏色</TH>
                  <TH className="text-right">自動匹配 min(USD/Mtok)</TH>
                  <TH className="text-right">自動匹配 max(USD/Mtok)</TH>
                  <TH className="text-right">排序</TH>
                  <TH className="text-right">操作</TH>
                </TR>
              </THead>
              <TBody>
                {items.map((t) => (
                  <TR key={t.tier_uid}>
                    <TD className="font-medium">{t.label_zh}</TD>
                    <TD className="text-muted-foreground">{t.label_en ?? "-"}</TD>
                    <TD className="font-mono text-sm">{t.key}</TD>
                    <TD>
                      <div className="flex items-center gap-2">
                        <span
                          aria-hidden
                          className="inline-block h-3 w-3 rounded-full border border-border"
                          style={{
                            backgroundColor: resolveColor(t.color) || "transparent",
                          }}
                        />
                        <span className="text-sm text-muted-foreground">
                          {t.color ?? "-"}
                        </span>
                      </div>
                    </TD>
                    <TD className="text-right font-mono text-sm">
                      {tokenToMtokInput(t.auto_match_min_price_per_mtok) || "-"}
                    </TD>
                    <TD className="text-right font-mono text-sm">
                      {tokenToMtokInput(t.auto_match_max_price_per_mtok) || "-"}
                    </TD>
                    <TD className="text-right">{t.sort_order}</TD>
                    <TD className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="編輯"
                          onClick={() => onOpenEdit(t)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="刪除"
                          onClick={() => {
                            setDeleteTarget(t);
                            setTierInUse(null);
                          }}
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

      {/* 建立 / 編輯 Dialog */}
      <Dialog
        open={mode !== null}
        onOpenChange={(o) => !o && setMode(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {mode?.kind === "edit" ? "編輯分級" : "新增分級"}
            </DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 pt-4">
            <FormField label="Key">
              <Input
                value={form.key}
                onChange={(e) => setForm({ ...form, key: e.target.value })}
                disabled={mode?.kind === "edit"}
                placeholder="cheap / standard / expensive ..."
                className="font-mono"
              />
              <p className="text-sm text-muted-foreground mt-1">
                建立後不可改;對應 models.tier_key。
              </p>
            </FormField>
            <FormField label="中文名稱">
              <Input
                value={form.label_zh}
                onChange={(e) => setForm({ ...form, label_zh: e.target.value })}
                placeholder="例如:經濟"
              />
            </FormField>
            <FormField label="英文名稱">
              <Input
                value={form.label_en}
                onChange={(e) => setForm({ ...form, label_en: e.target.value })}
                placeholder="例如:Cheap"
              />
            </FormField>
            <FormField label="顏色">
              <div className="flex items-center gap-2">
                <Input
                  value={form.color}
                  onChange={(e) => setForm({ ...form, color: e.target.value })}
                  placeholder="green / #10b981"
                />
                <span
                  aria-hidden
                  className="inline-block h-8 w-8 rounded-full border border-border shrink-0"
                  style={{
                    backgroundColor: resolveColor(form.color) || "transparent",
                  }}
                />
              </div>
              <p className="text-sm text-muted-foreground mt-1">
                可填 Tailwind palette 名(gray / green / blue / orange ...)或 hex(#10b981)。
              </p>
            </FormField>
            <FormField label="排序(數字越小越前)">
              <Input
                type="number"
                value={form.sort_order}
                onChange={(e) =>
                  setForm({ ...form, sort_order: e.target.value })
                }
              />
            </FormField>
            <div className="grid grid-cols-2 gap-3">
              <FormField label="自動匹配 min(USD/Mtok)">
                <Input
                  type="number"
                  step="0.000001"
                  value={form.auto_min}
                  onChange={(e) =>
                    setForm({ ...form, auto_min: e.target.value })
                  }
                  placeholder="USD/百萬 tokens"
                />
              </FormField>
              <FormField label="自動匹配 max(USD/Mtok)">
                <Input
                  type="number"
                  step="0.000001"
                  value={form.auto_max}
                  onChange={(e) =>
                    setForm({ ...form, auto_max: e.target.value })
                  }
                  placeholder="USD/百萬 tokens"
                />
              </FormField>
            </div>
            <p className="text-sm text-muted-foreground -mt-1">
              留空代表不參與自動分級;區間語義為 [min, max),max 留空表示無上限。
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
            <LoadingButton onClick={onSave} loading={saving}>
              儲存
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 刪除確認 — tier_in_use 時不關閉,改顯示錯誤訊息 */}
      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(o) => {
          if (!o) {
            setDeleteTarget(null);
            setTierInUse(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>刪除分級</DialogTitle>
          </DialogHeader>
          <div className="pt-3 flex flex-col gap-3 text-sm">
            {tierInUse === null ? (
              <p>
                將刪除「<b>{deleteTarget?.label_zh}</b>」(
                <code className="font-mono text-sm">{deleteTarget?.key}</code>
                )。確定嗎?
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                <p className="text-destructive font-medium">
                  此分級正在被以下模型使用,請先重新指派:
                </p>
                <div className="rounded-xl border border-border bg-muted/40 p-3 max-h-48 overflow-y-auto">
                  {tierInUse.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      (後端未提供使用清單)
                    </p>
                  ) : (
                    <ul className="font-mono text-sm space-y-1">
                      {tierInUse.map((id) => (
                        <li key={id}>{id}</li>
                      ))}
                    </ul>
                  )}
                </div>
                <Link
                  href="/admin/models"
                  className="text-primary hover:underline text-sm"
                >
                  → 前往「模型管理」重新指派
                </Link>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setDeleteTarget(null);
                setTierInUse(null);
              }}
              disabled={deleting}
            >
              {tierInUse !== null ? "關閉" : "取消"}
            </Button>
            {tierInUse === null && (
              <LoadingButton
                variant="destructive"
                onClick={onDelete}
                loading={deleting}
              >
                刪除
              </LoadingButton>
            )}
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
