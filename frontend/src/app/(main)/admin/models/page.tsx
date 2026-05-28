"use client";

import * as React from "react";
import { Plus, X } from "lucide-react";
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
import { FilterChip } from "@/components/ui/FilterChip";
import { Combobox } from "@/components/ui/Combobox";
import { SyncButton } from "@/components/admin/SyncButton";
import { useDialog } from "@/lib/dialog";
import { useToast } from "@/components/ui/toaster";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import type { Model, ModelTier, Paginated } from "@/types/api";
import { useAppSelector } from "@/store/hooks";

type AvailabilityFilter = "all" | "active" | "inactive";

const PAGE_SIZE = 20;

// 將 USD/token 顯示為每百萬 tokens 的價格(乘以 1_000_000),保留 4 位小數
function priceToMtokDisplay(perToken: string | null): string {
  if (perToken === null || perToken === undefined) return "-";
  const n = Number(perToken);
  if (!Number.isFinite(n)) return "-";
  if (n === 0) return "0";
  return (n * 1_000_000).toFixed(4);
}

// 卡片價格文字:無價格顯示「未提供」,有價格則為「$X/Mtoken」(M = 每百萬)
function cardPriceText(perToken: string | null): string {
  const display = priceToMtokDisplay(perToken);
  return display === "-" ? "未提供" : `$${display}/Mtoken`;
}

// 上下文長度:tokens 數除以 1024、四捨五入,以「ktokens」為單位顯示
function contextLengthDisplay(contextLength: number): string {
  return `${Math.round(contextLength / 1024)}ktokens`;
}

export default function ModelsAdminPage() {
  const role = useAppSelector((s) => s.auth.actor?.role);
  const { showDialog } = useDialog();
  const { toast } = useToast();

  // 後端一次回傳全部模型;分頁、搜尋、篩選一律前端處理
  const [items, setItems] = React.useState<Model[]>([]);
  const [tiers, setTiers] = React.useState<ModelTier[]>([]);
  const [loading, setLoading] = React.useState(true);

  // 工具列狀態
  const [selectedModelUid, setSelectedModelUid] = React.useState(""); // Combobox 搜尋:選中即定位該模型
  const [availability, setAvailability] = React.useState<AvailabilityFilter>("active");
  const [tierFilter, setTierFilter] = React.useState<string>("all"); // 'all' / '__none__' / tier.key

  // 前端分頁
  const [page, setPage] = React.useState(1);

  // Drawer
  const [editing, setEditing] = React.useState<Model | null>(null);
  const [editTier, setEditTier] = React.useState<string>("");
  const [savingEdit, setSavingEdit] = React.useState(false);

  // v1.2 新增本地模型 Dialog
  const [createOpen, setCreateOpen] = React.useState(false);
  const [createForm, setCreateForm] = React.useState({
    model_key: "",
    name: "",
    description: "",
    context_length: "",
    tier_key: "",
    modality: "text->text",
  });
  const [creating, setCreating] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const [list, tierList] = await Promise.all([
        apiClient.get<Paginated<Model>>(API_ENDPOINTS.models, {
          query: { include_inactive: 1 },
        }),
        apiClient.get<ModelTier[]>(API_ENDPOINTS.modelTiers),
      ]);
      setItems(list.items);
      setTiers(tierList);
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

  // 由 tier.key 取出該 tier 物件(顯示 label / color)
  const tierMap = React.useMemo(() => {
    const m: Record<string, ModelTier> = {};
    for (const t of tiers) m[t.key] = t;
    return m;
  }, [tiers]);

  // Combobox 選項:全部模型 + 各模型(label = 名稱,只以名稱搜尋)
  const modelOptions = React.useMemo(
    () => [
      { value: "", label: "全部模型" },
      ...[...items]
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((m) => ({ value: m.model_uid, label: m.name })),
    ],
    [items]
  );

  // 前端過濾:選中模型則只顯示該筆,否則依可用性 + 分級篩選
  const visible = React.useMemo(() => {
    if (selectedModelUid) {
      return items.filter((it) => it.model_uid === selectedModelUid);
    }
    return items.filter((it) => {
      if (availability === "active" && !it.is_active) return false;
      if (availability === "inactive" && it.is_active) return false;
      if (tierFilter === "__none__") {
        if (it.tier_key) return false;
      } else if (tierFilter !== "all" && it.tier_key !== tierFilter) {
        return false;
      }
      return true;
    });
  }, [items, selectedModelUid, availability, tierFilter]);

  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const pageSafe = Math.min(page, totalPages);
  const pageItems = visible.slice(
    (pageSafe - 1) * PAGE_SIZE,
    pageSafe * PAGE_SIZE
  );

  if (role !== "admin") {
    return (
      <>
        <PageTitle title="模型管理" />
        <Card>
          <CardContent className="pt-6">
            <EmptyState title="權限不足" description="本頁僅限 admin 存取" />
          </CardContent>
        </Card>
      </>
    );
  }

  // 切換 is_active(立即 PATCH)
  const onToggleActive = async (m: Model) => {
    try {
      await apiClient.patch(API_ENDPOINTS.modelById(m.model_uid), {
        is_active: !m.is_active,
      });
      toast(`${m.name} 已${!m.is_active ? "啟用" : "停用"}`, "success");
      // 直接 in-place 更新,避免整批 reload
      setItems((arr) =>
        arr.map((x) =>
          x.model_uid === m.model_uid ? { ...x, is_active: !m.is_active } : x
        )
      );
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "操作失敗",
          message: err.localizedDetail,
        });
      }
    }
  };

  // 開啟編輯 Drawer
  const onRowClick = (m: Model) => {
    setEditing(m);
    setEditTier(m.tier_key ?? "");
  };

  const onCreateInternal = async () => {
    if (!createForm.model_key.trim() || !createForm.name.trim()) {
      showDialog({
        type: "warning",
        title: "欄位未填",
        message: "請至少填入 Model Key 與名稱",
      });
      return;
    }
    setCreating(true);
    try {
      await apiClient.post<Model>(API_ENDPOINTS.models, {
        provider: "internal",
        model_key: createForm.model_key.trim(),
        name: createForm.name.trim(),
        description: createForm.description.trim() || null,
        context_length: createForm.context_length
          ? Number(createForm.context_length)
          : null,
        modality: createForm.modality || null,
        tier_key: createForm.tier_key || null,
      });
      toast("本地模型已新增", "success");
      setCreateOpen(false);
      setCreateForm({
        model_key: "",
        name: "",
        description: "",
        context_length: "",
        tier_key: "",
        modality: "text->text",
      });
      load();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "建立失敗",
          message: err.localizedDetail,
        });
      }
    } finally {
      setCreating(false);
    }
  };

  const onSaveEdit = async () => {
    if (!editing) return;
    setSavingEdit(true);
    try {
      const next = editTier === "" ? null : editTier;
      const updated = await apiClient.patch<Model>(
        API_ENDPOINTS.modelById(editing.model_uid),
        { tier_key: next }
      );
      setItems((arr) =>
        arr.map((x) => (x.model_uid === editing.model_uid ? updated : x))
      );
      toast("分級已更新", "success");
      setEditing(null);
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "儲存失敗",
          message: err.localizedDetail,
        });
      }
    } finally {
      setSavingEdit(false);
    }
  };

  return (
    <>
      <PageTitle
        title="模型管理"
        description="模型白名單 — OpenRouter 走「同步」自動拉取"
        actions={
          <div className="flex shrink-0 items-center gap-2">
            {/* 本地模型功能暫時停用 — 隱藏「新增本地模型」入口(待實際導入企業內部模型再開啟)
            <Button
              variant="outline"
              className="whitespace-nowrap"
              onClick={() => setCreateOpen(true)}
              disabled
              title="本地模型新增功能暫停開放"
            >
              <Plus className="h-4 w-4" />
              新增本地模型
            </Button>
            */}
            <SyncButton
              endpoint={API_ENDPOINTS.syncModels}
              onSuccess={() => load()}
              className="whitespace-nowrap"
            />
          </div>
        }
      />

      <Card>
        <CardContent className="pt-6 flex flex-col gap-4">
          {/* 搜尋 Combobox + Filter chips */}
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-20 shrink-0 text-sm text-muted-foreground">
                搜尋：
              </span>
              <Combobox
                className="w-full sm:w-96"
                options={modelOptions}
                value={selectedModelUid}
                onChange={(v) => {
                  setSelectedModelUid(v);
                  setPage(1);
                }}
                placeholder="輸入模型名稱搜尋..."
                searchPlaceholder="輸入模型名稱..."
                emptyText="查無模型"
              />
            </div>

            {/* 可用性 + 分級 — 同列水平排列 */}
            <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="w-20 shrink-0 text-sm text-muted-foreground">
                  可用性：
                </span>
                <FilterChip
                  active={availability === "all"}
                  onClick={() => {
                    setAvailability("all");
                    setPage(1);
                  }}
                >
                  全部
                </FilterChip>
                <FilterChip
                  active={availability === "active"}
                  onClick={() => {
                    setAvailability("active");
                    setPage(1);
                  }}
                >
                  已啟用
                </FilterChip>
                <FilterChip
                  active={availability === "inactive"}
                  onClick={() => {
                    setAvailability("inactive");
                    setPage(1);
                  }}
                >
                  已停用
                </FilterChip>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="shrink-0 text-sm text-muted-foreground">
                  分級：
                </span>
                <FilterChip
                  active={tierFilter === "all"}
                  onClick={() => {
                    setTierFilter("all");
                    setPage(1);
                  }}
                >
                  全部
                </FilterChip>
                <FilterChip
                  active={tierFilter === "__none__"}
                  onClick={() => {
                    setTierFilter("__none__");
                    setPage(1);
                  }}
                >
                  未分級
                </FilterChip>
                {tiers.map((t) => (
                  <FilterChip
                    key={t.tier_uid}
                    active={tierFilter === t.key}
                    onClick={() => {
                      setTierFilter(t.key);
                      setPage(1);
                    }}
                  >
                    {t.label_zh}
                  </FilterChip>
                ))}
              </div>
            </div>

            {selectedModelUid && (
              <p className="text-sm text-muted-foreground">
                已鎖定單一模型;清為「全部模型」後可依可用性 / 分級瀏覽。
              </p>
            )}
          </div>

          {loading ? (
            <div className="flex flex-col gap-3">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : visible.length === 0 ? (
            <EmptyState
              title="尚無資料"
              description="調整篩選條件,或執行同步以從 OpenRouter 取得最新清單"
            />
          ) : (
            <>
              {/* >= xl 表格 */}
              <div className="hidden xl:block">
                <Table>
                  <THead>
                    <TR>
                      <TH>名稱</TH>
                      <TH>來源</TH>
                      <TH>Model Key</TH>
                      <TH>分級</TH>
                      <TH className="text-right">上下文長度</TH>
                      <TH>模態</TH>
                      <TH className="text-right">輸入價格(US$ / 每百萬 tokens)</TH>
                      <TH className="text-right">輸出價格(US$ / 每百萬 tokens)</TH>
                      <TH>狀態</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {pageItems.map((m) => (
                      <TR
                        key={m.model_uid}
                        className="hover:cursor-pointer"
                        onClick={() => onRowClick(m)}
                      >
                        <TD>
                          <div className="font-medium">{m.name}</div>
                        </TD>
                        <TD>
                          <ProviderBadge provider={m.provider} />
                        </TD>
                        <TD className="font-mono text-sm text-muted-foreground whitespace-nowrap">
                          {m.model_key}
                        </TD>
                        <TD>
                          <TierBadge
                            tierKey={m.tier_key}
                            tier={m.tier_key ? tierMap[m.tier_key] : undefined}
                          />
                        </TD>
                        <TD className="text-right font-mono text-sm">
                          {m.context_length != null
                            ? contextLengthDisplay(m.context_length)
                            : "-"}
                        </TD>
                        <TD className="text-sm">
                          {m.modality ? m.modality.replace("->", " → ") : "-"}
                        </TD>
                        <TD className="text-right font-mono text-sm">
                          {priceToMtokDisplay(m.price_prompt_per_token)}
                        </TD>
                        <TD className="text-right font-mono text-sm">
                          {priceToMtokDisplay(m.price_completion_per_token)}
                        </TD>
                        <TD onClick={(e) => e.stopPropagation()}>
                          <Switch
                            checked={m.is_active}
                            onChange={() => onToggleActive(m)}
                          />
                        </TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </div>

              {/* < xl 卡片 */}
              <div className="xl:hidden flex flex-col gap-3">
                {pageItems.map((m) => (
                  <button
                    key={m.model_uid}
                    type="button"
                    onClick={() => onRowClick(m)}
                    className="text-left rounded-xl border border-border bg-background p-4 hover:bg-muted/40 hover:cursor-pointer flex flex-col gap-2"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <div className="font-medium truncate">{m.name}</div>
                          <ProviderBadge provider={m.provider} />
                        </div>
                        <div className="text-sm font-mono text-muted-foreground truncate">
                          {m.model_key}
                        </div>
                      </div>
                      <div
                        onClick={(e) => e.stopPropagation()}
                        className="shrink-0"
                      >
                        <Switch
                          checked={m.is_active}
                          onChange={() => onToggleActive(m)}
                        />
                      </div>
                    </div>
                    <div className="flex flex-col gap-1.5 text-sm">
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">分級:</span>
                          <TierBadge
                            tierKey={m.tier_key}
                            tier={m.tier_key ? tierMap[m.tier_key] : undefined}
                          />
                        </div>
                        <div>
                          <span className="text-muted-foreground">模態:</span>{" "}
                          {m.modality
                            ? m.modality.replace("->", " → ")
                            : "未指定"}
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
                        <div>
                          <span className="text-muted-foreground">
                            上下文長度:
                          </span>{" "}
                          {m.context_length != null
                            ? contextLengthDisplay(m.context_length)
                            : "未指定"}
                        </div>
                        <div>
                          <span className="text-muted-foreground">
                            輸入/輸出:
                          </span>{" "}
                          {cardPriceText(m.price_prompt_per_token)},{" "}
                          {cardPriceText(m.price_completion_per_token)}
                        </div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </>
          )}

          {!loading && visible.length > 0 && (
            <div className="flex items-center justify-between text-sm text-muted-foreground pt-2">
              <span>
                第 {pageSafe} / {totalPages} 頁(共 {visible.length} 筆;本頁顯示 {pageItems.length})
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={pageSafe <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  上一頁
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={pageSafe >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  下一頁
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 編輯 Drawer(以 Dialog 模擬,行動版自然轉中央彈窗) */}
      <Dialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
      >
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>{editing?.name ?? "模型詳情"}</DialogTitle>
          </DialogHeader>
          {editing && (
            <div className="flex flex-col gap-4 pt-3 max-h-[70vh] overflow-y-auto">
              <Field label="Provider / Model Key">
                <div className="flex items-center gap-2 flex-wrap">
                  <ProviderBadge provider={editing.provider} />
                  <code className="text-sm font-mono break-all">
                    {editing.model_key}
                  </code>
                </div>
              </Field>
              {editing.description && (
                <Field label="說明">
                  <p className="text-sm leading-relaxed text-foreground/80 whitespace-pre-wrap">
                    {editing.description}
                  </p>
                </Field>
              )}
              <div className="grid grid-cols-2 gap-4">
                <Field label="上下文長度">
                  <span className="font-mono text-sm">
                    {editing.context_length != null
                      ? contextLengthDisplay(editing.context_length)
                      : "未指定"}
                  </span>
                </Field>
                <Field label="最大輸出長度">
                  <span className="font-mono text-sm">
                    {editing.max_completion_tokens != null
                      ? `${editing.max_completion_tokens.toLocaleString()} tokens`
                      : "未指定"}
                  </span>
                </Field>
                <Field label="模態">
                  <span className="text-sm">
                    {editing.modality
                      ? editing.modality.replace("->", " → ")
                      : "未指定"}
                  </span>
                </Field>
                <Field label="斷詞器 (Tokenizer)">
                  <span className="text-sm">{editing.tokenizer ?? "未指定"}</span>
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Field label="輸入價格(US$ / 每百萬 tokens)">
                  <span className="font-mono text-sm">
                    {priceToMtokDisplay(editing.price_prompt_per_token)}
                  </span>
                </Field>
                <Field label="輸出價格(US$ / 每百萬 tokens)">
                  <span className="font-mono text-sm">
                    {priceToMtokDisplay(editing.price_completion_per_token)}
                  </span>
                </Field>
                <Field label="圖片價格(US$ / 每張)">
                  <span className="font-mono text-sm">
                    {editing.price_image_per_image ?? "未提供"}
                  </span>
                </Field>
                <Field label="請求價格(US$ / 每次)">
                  <span className="font-mono text-sm">
                    {editing.price_request_flat ?? "未提供"}
                  </span>
                </Field>
              </div>

              <div className="border-t border-border pt-3">
                <Label>分級</Label>
                <select
                  value={editTier}
                  onChange={(e) => setEditTier(e.target.value)}
                  className="mt-1.5 h-10 w-full rounded-xl border border-border bg-background px-3 text-sm hover:cursor-pointer"
                >
                  <option value="">未分級</option>
                  {tiers.map((t) => (
                    <option key={t.tier_uid} value={t.key}>
                      {t.label_zh}({t.key})
                    </option>
                  ))}
                </select>
                <p className="text-sm text-muted-foreground mt-2">
                  分級用於後續限制不同角色 / Skill 可使用的模型;當前僅儲存,未強制執行。
                </p>
              </div>

              <div className="text-sm text-muted-foreground">
                最近同步:{new Date(editing.last_synced_at).toLocaleString("zh-TW", { hour12: false })}
              </div>
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEditing(null)}
              disabled={savingEdit}
            >
              <X className="h-4 w-4" /> 取消
            </Button>
            <LoadingButton onClick={onSaveEdit} loading={savingEdit}>
              儲存分級
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 新增本地模型 Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>新增本地模型</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 pt-3">
            <div className="flex flex-col gap-1.5">
              <Label>Model Key *</Label>
              <Input
                value={createForm.model_key}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, model_key: e.target.value }))
                }
                placeholder="internal/llama3-70b"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label>名稱 *</Label>
                <Input
                  value={createForm.name}
                  onChange={(e) =>
                    setCreateForm((f) => ({ ...f, name: e.target.value }))
                  }
                  placeholder="Llama 3 70B (內部)"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>分級</Label>
                <select
                  value={createForm.tier_key}
                  onChange={(e) =>
                    setCreateForm((f) => ({ ...f, tier_key: e.target.value }))
                  }
                  className="h-10 w-full rounded-xl border border-border bg-background px-3 text-sm hover:cursor-pointer"
                >
                  <option value="">(未分級)</option>
                  {tiers.map((t) => (
                    <option key={t.tier_uid} value={t.key}>
                      {t.label_zh}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label>Context Length</Label>
                <Input
                  type="number"
                  value={createForm.context_length}
                  onChange={(e) =>
                    setCreateForm((f) => ({
                      ...f,
                      context_length: e.target.value,
                    }))
                  }
                  placeholder="8192"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Modality</Label>
                <Input
                  value={createForm.modality}
                  onChange={(e) =>
                    setCreateForm((f) => ({ ...f, modality: e.target.value }))
                  }
                  placeholder="text->text"
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>說明</Label>
              <Input
                value={createForm.description}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, description: e.target.value }))
                }
                placeholder="vLLM,4-bit 量化"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCreateOpen(false)}
              disabled={creating}
            >
              取消
            </Button>
            <LoadingButton onClick={onCreateInternal} loading={creating}>
              建立
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function ProviderBadge({ provider }: { provider: "openrouter" | "internal" }) {
  if (provider === "internal") {
    return (
      <span className="inline-flex items-center rounded-full border border-purple-500/30 bg-purple-500/10 text-purple-600 px-2 py-0.5 text-sm font-medium">
        Internal
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full border border-blue-500/30 bg-blue-500/10 text-blue-600 px-2 py-0.5 text-sm font-medium">
      OpenRouter
    </span>
  );
}

function TierBadge({
  tierKey,
  tier,
}: {
  tierKey: string | null;
  tier: ModelTier | undefined;
}) {
  if (!tierKey) {
    return (
      <span className="inline-flex items-center rounded-full border border-border bg-muted text-muted-foreground px-2 py-0.5 text-sm font-medium">
        未分級
      </span>
    );
  }
  // 動態套色:tier.color 可能是 Tailwind palette 名(如 'green') 或 hex
  // 為簡化,以 inline style 標準化為背景圓點 + 文字
  const colorRaw = tier?.color ?? "";
  const isHex = /^#?[0-9a-fA-F]{3,8}$/.test(colorRaw);
  const tailwindMap: Record<string, string> = {
    gray: "#9ca3af",
    green: "#10b981",
    blue: "#3b82f6",
    orange: "#f97316",
    red: "#ef4444",
    purple: "#a855f7",
    yellow: "#eab308",
  };
  let dotColor = "";
  if (isHex) {
    dotColor = colorRaw.startsWith("#") ? colorRaw : `#${colorRaw}`;
  } else if (colorRaw && tailwindMap[colorRaw]) {
    dotColor = tailwindMap[colorRaw];
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-2 py-0.5 text-sm font-medium">
      {dotColor && (
        <span
          aria-hidden
          className="inline-block h-2 w-2 rounded-full"
          style={{ backgroundColor: dotColor }}
        />
      )}
      {tier?.label_zh ?? tierKey}
    </span>
  );
}

// 自製 Switch:click → toggle;搭配父 onChange 立即觸發 PATCH
function Switch({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={onChange}
      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors hover:cursor-pointer ${
        checked ? "bg-primary" : "bg-muted"
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-card transition-transform ${
          checked ? "translate-x-4" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm text-muted-foreground">{label}</span>
      {children}
    </div>
  );
}
