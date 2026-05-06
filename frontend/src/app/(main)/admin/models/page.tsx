"use client";

import * as React from "react";
import { Search, X } from "lucide-react";
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
import { SyncButton } from "@/components/admin/SyncButton";
import { useDialog } from "@/lib/dialog";
import { useToast } from "@/components/ui/toaster";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import type { Model, ModelTier, Paginated } from "@/types/api";
import { useAppSelector } from "@/store/hooks";

type AvailabilityFilter = "all" | "active" | "inactive";

// 將 USD/token 顯示為 USD/M tokens(乘以 1_000_000),保留 4 位小數
function priceToMtokDisplay(perToken: string | null): string {
  if (perToken === null || perToken === undefined) return "-";
  const n = Number(perToken);
  if (!Number.isFinite(n)) return "-";
  if (n === 0) return "0";
  return (n * 1_000_000).toFixed(4);
}

export default function ModelsAdminPage() {
  const role = useAppSelector((s) => s.auth.actor?.role);
  const { showDialog } = useDialog();
  const { toast } = useToast();

  const [items, setItems] = React.useState<Model[]>([]);
  const [tiers, setTiers] = React.useState<ModelTier[]>([]);
  const [loading, setLoading] = React.useState(true);

  // 工具列狀態
  const [search, setSearch] = React.useState("");
  const [availability, setAvailability] = React.useState<AvailabilityFilter>("active");
  const [tierFilter, setTierFilter] = React.useState<string>("all"); // 'all' / tier.key

  // 分頁(後端列表)
  const [page, setPage] = React.useState(1);
  const [total, setTotal] = React.useState(0);
  const size = 20;

  // Drawer
  const [editing, setEditing] = React.useState<Model | null>(null);
  const [editTier, setEditTier] = React.useState<string>("");
  const [savingEdit, setSavingEdit] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const query: Record<string, string | number> = { page, size };
      if (availability === "inactive" || availability === "all") {
        query.include_inactive = 1;
      }
      // tier_filter 改走後端 query,避免 size=20 時跨頁過濾不到目標
      if (tierFilter !== "all" && tierFilter !== "__none__") {
        query.tier_key = tierFilter;
      }
      const [list, tierList] = await Promise.all([
        apiClient.get<Paginated<Model>>(API_ENDPOINTS.models, { query }),
        apiClient.get<ModelTier[]>(API_ENDPOINTS.modelTiers),
      ]);
      setItems(list.items);
      setTotal(list.total);
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
  }, [page, availability, tierFilter, showDialog]);

  React.useEffect(() => {
    if (role === "admin") load();
  }, [load, role]);

  // 由 tier.key 取出該 tier 物件(顯示 label / color)
  const tierMap = React.useMemo(() => {
    const m: Record<string, ModelTier> = {};
    for (const t of tiers) m[t.key] = t;
    return m;
  }, [tiers]);

  // 前端過濾(搜尋 + tier + availability of in-list items)
  const visible = React.useMemo(() => {
    const kw = search.trim().toLowerCase();
    return items.filter((it) => {
      if (availability === "active" && !it.is_active) return false;
      if (availability === "inactive" && it.is_active) return false;
      if (tierFilter !== "all") {
        if (tierFilter === "__none__") {
          if (it.tier_key) return false;
        } else if (it.tier_key !== tierFilter) {
          return false;
        }
      }
      if (kw) {
        const hay = `${it.name} ${it.openrouter_model_id}`.toLowerCase();
        if (!hay.includes(kw)) return false;
      }
      return true;
    });
  }, [items, search, availability, tierFilter]);

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
        description="OpenRouter 模型主檔;同步、分級、啟停由此控管"
        actions={
          <SyncButton
            endpoint={API_ENDPOINTS.syncModels}
            onSuccess={() => load()}
          />
        }
      />

      <Card>
        <CardContent className="pt-6 flex flex-col gap-4">
          {/* 搜尋 + Filter chips */}
          <div className="flex flex-col gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="搜尋模型名稱或 ID(client-side filter)"
                className="pl-9"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className="shrink-0 text-sm text-muted-foreground">
                按可用性:
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
                按分級:
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
                      <TH>OpenRouter ID</TH>
                      <TH>分級</TH>
                      <TH className="text-right">Context</TH>
                      <TH>Modality</TH>
                      <TH className="text-right">Prompt $/Mtok</TH>
                      <TH className="text-right">Completion $/Mtok</TH>
                      <TH>狀態</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {visible.map((m) => (
                      <TR
                        key={m.model_uid}
                        className="hover:cursor-pointer"
                        onClick={() => onRowClick(m)}
                      >
                        <TD>
                          <div className="font-medium">{m.name}</div>
                        </TD>
                        <TD className="font-mono text-sm text-muted-foreground whitespace-nowrap">
                          {m.openrouter_model_id}
                        </TD>
                        <TD>
                          <TierBadge
                            tierKey={m.tier_key}
                            tier={m.tier_key ? tierMap[m.tier_key] : undefined}
                          />
                        </TD>
                        <TD className="text-right font-mono text-sm">
                          {m.context_length?.toLocaleString() ?? "-"}
                        </TD>
                        <TD className="text-sm">{m.modality ?? "-"}</TD>
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
                {visible.map((m) => (
                  <button
                    key={m.model_uid}
                    type="button"
                    onClick={() => onRowClick(m)}
                    className="text-left rounded-xl border border-border bg-background p-4 hover:bg-muted/40 hover:cursor-pointer flex flex-col gap-2"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="font-medium truncate">{m.name}</div>
                        <div className="text-sm font-mono text-muted-foreground truncate">
                          {m.openrouter_model_id}
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
                    <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                      <TierBadge
                        tierKey={m.tier_key}
                        tier={m.tier_key ? tierMap[m.tier_key] : undefined}
                      />
                      {m.modality && <span>{m.modality}</span>}
                      {m.context_length != null && (
                        <span>ctx {m.context_length.toLocaleString()}</span>
                      )}
                    </div>
                    <div className="text-sm font-mono text-muted-foreground">
                      Prompt ${priceToMtokDisplay(m.price_prompt_per_token)} /
                      Mtok · Completion $
                      {priceToMtokDisplay(m.price_completion_per_token)} / Mtok
                    </div>
                  </button>
                ))}
              </div>
            </>
          )}

          {!loading && total > 0 && (
            <div className="flex items-center justify-between text-sm text-muted-foreground pt-2">
              <span>
                第 {page} / {Math.max(1, Math.ceil(total / size))} 頁(共 {total} 筆;本頁顯示 {visible.length})
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
                  disabled={page * size >= total}
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
              <Field label="OpenRouter ID">
                <code className="text-sm font-mono break-all">
                  {editing.openrouter_model_id}
                </code>
              </Field>
              {editing.description && (
                <Field label="說明">
                  <p className="text-sm leading-relaxed text-foreground/80 whitespace-pre-wrap">
                    {editing.description}
                  </p>
                </Field>
              )}
              <div className="grid grid-cols-2 gap-4">
                <Field label="Context Length">
                  <span className="font-mono text-sm">
                    {editing.context_length?.toLocaleString() ?? "-"}
                  </span>
                </Field>
                <Field label="Max Completion">
                  <span className="font-mono text-sm">
                    {editing.max_completion_tokens?.toLocaleString() ?? "-"}
                  </span>
                </Field>
                <Field label="Modality">
                  <span className="text-sm">{editing.modality ?? "-"}</span>
                </Field>
                <Field label="Tokenizer">
                  <span className="text-sm">{editing.tokenizer ?? "-"}</span>
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Field label="Prompt 價(USD/Mtok)">
                  <span className="font-mono text-sm">
                    {priceToMtokDisplay(editing.price_prompt_per_token)}
                  </span>
                </Field>
                <Field label="Completion 價(USD/Mtok)">
                  <span className="font-mono text-sm">
                    {priceToMtokDisplay(editing.price_completion_per_token)}
                  </span>
                </Field>
                <Field label="Image 價(USD/image)">
                  <span className="font-mono text-sm">
                    {editing.price_image_per_image ?? "-"}
                  </span>
                </Field>
                <Field label="Request 價(USD/req)">
                  <span className="font-mono text-sm">
                    {editing.price_request_flat ?? "-"}
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
    </>
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
