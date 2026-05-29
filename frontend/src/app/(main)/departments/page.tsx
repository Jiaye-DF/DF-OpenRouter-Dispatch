"use client";

import * as React from "react";
import {
  Copy,
  KeyRound,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
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
import { useConfirm } from "@/components/common/ConfirmDialog";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import type { Department, Paginated, SdkKey } from "@/types/api";
import { useAppSelector } from "@/store/hooks";

interface FormState {
  department_uid?: string;
  code: string;
  name: string;
  description: string;
  first_key_name: string;
}

const EMPTY_FORM: FormState = {
  code: "",
  name: "",
  description: "",
  first_key_name: "",
};

// 部門頁(v1.6 合併 SDK Key 管理):列表 + 建立 / 編輯 Dialog + 軟刪除;
// 每個部門 row 可展開檢視 / 管理該部門的 SDK Keys;
// 建立部門時連同建第 1 把 SDK Key,明文一次性彈窗顯示。
export default function DepartmentsPage() {
  const isAdmin = useAppSelector((s) => s.auth.actor?.role === "admin");
  const { showDialog } = useDialog();
  const { confirm } = useConfirm();
  const { toast } = useToast();

  const [items, setItems] = React.useState<Department[]>([]);
  const [keysByDept, setKeysByDept] = React.useState<Record<string, SdkKey[]>>({});
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set());
  const [loading, setLoading] = React.useState(true);
  const [page, setPage] = React.useState(1);
  const [total, setTotal] = React.useState(0);

  // 部門 Dialog
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [form, setForm] = React.useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = React.useState(false);

  // 建立完成後一次性顯示明文
  const [newKeyPlain, setNewKeyPlain] = React.useState<string | null>(null);

  // sub-section「+ 新增 SDK Key」inline input(依 dept_uid 保存名稱草稿)
  const [newKeyDraft, setNewKeyDraft] = React.useState<Record<string, string>>({});
  const [addingKeyDeptUid, setAddingKeyDeptUid] = React.useState<string | null>(null);

  const size = 20;

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const [deptResp, keyResp] = await Promise.all([
        apiClient.get<Paginated<Department>>(API_ENDPOINTS.departments, {
          query: { page, size },
        }),
        // admin 才允許讀 sdk-keys 列表;非 admin 不抓(後端會 403)
        isAdmin
          ? apiClient.get<Paginated<SdkKey>>(API_ENDPOINTS.sdkKeys, {
              query: { page: 1, size: 200 },
            })
          : Promise.resolve({ items: [], total: 0, page: 1, size: 0 } as Paginated<SdkKey>),
      ]);
      setItems(deptResp.items);
      setTotal(deptResp.total);
      const grouped: Record<string, SdkKey[]> = {};
      for (const k of keyResp.items) {
        (grouped[k.department_uid] ??= []).push(k);
      }
      setKeysByDept(grouped);
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "載入失敗", message: err.localizedDetail });
      }
    } finally {
      setLoading(false);
    }
  }, [page, isAdmin, showDialog]);

  React.useEffect(() => {
    load();
  }, [load]);

  // 重抓 SDK Keys(不重抓部門列表,避免 toggle/delete 後 page 跳動)
  const reloadKeys = React.useCallback(async () => {
    if (!isAdmin) return;
    try {
      const resp = await apiClient.get<Paginated<SdkKey>>(API_ENDPOINTS.sdkKeys, {
        query: { page: 1, size: 200 },
      });
      const grouped: Record<string, SdkKey[]> = {};
      for (const k of resp.items) {
        (grouped[k.department_uid] ??= []).push(k);
      }
      setKeysByDept(grouped);
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "載入失敗", message: err.localizedDetail });
      }
    }
  }, [isAdmin, showDialog]);

  const toggleExpand = (uid: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(uid)) next.delete(uid);
      else next.add(uid);
      return next;
    });
  };

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
      first_key_name: "", // 編輯時不顯示此欄
    });
    setDialogOpen(true);
  };

  const onSave = async () => {
    if (!form.name.trim()) {
      showDialog({ type: "warning", title: "欄位未填", message: "請輸入部門名稱" });
      return;
    }
    if (!form.department_uid && !form.code.trim()) {
      showDialog({ type: "warning", title: "欄位未填", message: "請輸入部門代碼" });
      return;
    }
    setSaving(true);
    try {
      if (form.department_uid) {
        // 編輯:code 建立後不可改
        await apiClient.patch(API_ENDPOINTS.departmentById(form.department_uid), {
          name: form.name.trim(),
          description: form.description.trim() || null,
        });
        setDialogOpen(false);
        setForm(EMPTY_FORM);
        setPage(1);
        await load();
      } else {
        // 新建:dept → sdk-key 兩步串接
        const created = await apiClient.post<Department>(API_ENDPOINTS.departments, {
          code: form.code.trim(),
          name: form.name.trim(),
          description: form.description.trim() || null,
        });
        const keyName =
          form.first_key_name.trim() || `${form.name.trim()} 主金鑰`;
        try {
          const keyResp = await apiClient.post<{ key: string }>(
            API_ENDPOINTS.sdkKeys,
            {
              department_uid: created.department_uid,
              name: keyName,
            }
          );
          setNewKeyPlain(keyResp?.key ?? null);
          // 主金鑰建好後預設展開,使用者可立刻在 row 下方看到
          setExpanded((prev) => {
            const next = new Set(prev);
            next.add(created.department_uid);
            return next;
          });
        } catch (err) {
          // 部門建好、key 沒建成 — 不擋使用者,只警告,使用者可從 row 展開後手動補建
          if (err instanceof ApiError) {
            showDialog({
              type: "warning",
              title: "部門已建立,但主金鑰建立失敗",
              message: `${err.localizedDetail}\n請從部門 row 展開後手動補建。`,
            });
          }
        }
        setDialogOpen(false);
        setForm(EMPTY_FORM);
        setPage(1);
        await load();
      }
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "儲存失敗", message: err.localizedDetail });
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
          將軟刪除「<b>{d.name}</b>」,僅在部門下無啟用的 Key / 專案 / 使用者時才可成功,確定嗎?
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
        showDialog({ type: "error", title: "刪除失敗", message: err.localizedDetail });
      }
    }
  };

  // ── SDK Key 操作 ──
  const onAddKey = async (d: Department) => {
    const draft = (newKeyDraft[d.department_uid] ?? "").trim();
    if (!draft) {
      showDialog({
        type: "warning",
        title: "欄位未填",
        message: "請輸入新金鑰名稱",
      });
      return;
    }
    setAddingKeyDeptUid(d.department_uid);
    try {
      const resp = await apiClient.post<{ key: string }>(API_ENDPOINTS.sdkKeys, {
        department_uid: d.department_uid,
        name: draft,
      });
      setNewKeyDraft((m) => ({ ...m, [d.department_uid]: "" }));
      setNewKeyPlain(resp?.key ?? null);
      await reloadKeys();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "建立失敗", message: err.localizedDetail });
      }
    } finally {
      setAddingKeyDeptUid(null);
    }
  };

  const onToggleKey = async (k: SdkKey) => {
    try {
      await apiClient.patch(API_ENDPOINTS.sdkKeyById(k.sdk_api_key_uid), {
        is_active: !k.is_active,
      });
      await reloadKeys();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "操作失敗", message: err.localizedDetail });
      }
    }
  };

  const onDeleteKey = async (k: SdkKey) => {
    const ok = await confirm({
      title: "刪除 SDK Key",
      message: `將軟刪除「${k.name}」,確定嗎?`,
      destructive: true,
    });
    if (!ok) return;
    try {
      await apiClient.delete(API_ENDPOINTS.sdkKeyById(k.sdk_api_key_uid));
      await reloadKeys();
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "刪除失敗", message: err.localizedDetail });
      }
    }
  };

  const copyPlain = (k: SdkKey) => {
    if (!k.key_values) return;
    navigator.clipboard
      .writeText(k.key_values)
      .then(() => toast("已複製部門金鑰", "success"))
      .catch(() => {});
  };

  const totalPages = Math.max(1, Math.ceil(total / size));

  return (
    <>
      <PageTitle
        title="部門管理"
        description="部門為金鑰與專案的載體;展開 row 可管理該部門的 SDK Key(部門金鑰)"
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
                  {isAdmin && <TH>操作</TH>}
                  <TH>代碼</TH>
                  <TH>名稱</TH>
                  <TH>描述</TH>
                  <TH>狀態</TH>
                  {isAdmin && <TH className="text-right">部門金鑰</TH>}
                </TR>
              </THead>
              <TBody>
                {items.map((d) => {
                  const keys = keysByDept[d.department_uid] ?? [];
                  const isOpen = expanded.has(d.department_uid);
                  return (
                    <React.Fragment key={d.department_uid}>
                      <TR>
                        {isAdmin && (
                          <TD>
                            <div className="flex gap-1">
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
                            <button
                              type="button"
                              aria-expanded={isOpen}
                              aria-label={
                                isOpen ? "收合部門金鑰" : "展開部門金鑰"
                              }
                              onClick={() => toggleExpand(d.department_uid)}
                              className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm transition-colors hover:bg-muted hover:cursor-pointer ${
                                isOpen ? "text-primary" : "text-muted-foreground"
                              }`}
                            >
                              <KeyRound className="h-4 w-4" />
                              {keys.length}
                            </button>
                          </TD>
                        )}
                      </TR>
                      {isAdmin && isOpen && (
                        <TR>
                          <TD colSpan={6} className="bg-muted/30 p-0">
                            <DepartmentKeysPanel
                              dept={d}
                              keys={keys}
                              draft={newKeyDraft[d.department_uid] ?? ""}
                              setDraft={(v) =>
                                setNewKeyDraft((m) => ({
                                  ...m,
                                  [d.department_uid]: v,
                                }))
                              }
                              onAdd={() => onAddKey(d)}
                              adding={addingKeyDeptUid === d.department_uid}
                              onToggle={onToggleKey}
                              onDelete={onDeleteKey}
                              onCopy={copyPlain}
                            />
                          </TD>
                        </TR>
                      )}
                    </React.Fragment>
                  );
                })}
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
              <Label htmlFor="dept-code">
                代碼
                {form.department_uid && (
                  <span className="ml-2 text-sm text-muted-foreground">
                    (建立後不可修改)
                  </span>
                )}
              </Label>
              <Input
                id="dept-code"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                placeholder="例:T000"
                disabled={!!form.department_uid}
                readOnly={!!form.department_uid}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="dept-name">名稱</Label>
              <Input
                id="dept-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="例:資訊部"
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
            {!form.department_uid && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="dept-first-key">主金鑰名稱</Label>
                <Input
                  id="dept-first-key"
                  value={form.first_key_name}
                  onChange={(e) =>
                    setForm({ ...form, first_key_name: e.target.value })
                  }
                  placeholder={`留空預設「${form.name.trim() || "(部門名稱)"} 主金鑰」`}
                />
                <p className="text-sm text-muted-foreground">
                  建立部門時會同步產生第 1 把 SDK Key,明文僅一次性彈窗顯示。
                </p>
              </div>
            )}
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

      {/* 建立完成後一次性顯示明文(同時也可從 row 展開後重新複製) */}
      <Dialog
        open={newKeyPlain !== null}
        onOpenChange={(o) => !o && setNewKeyPlain(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>部門金鑰</DialogTitle>
          </DialogHeader>
          <div className="pt-4 flex flex-col gap-2">
            <p className="text-sm text-muted-foreground">
              已建立完成,亦可從部門 row 展開後隨時複製。
            </p>
            <div className="rounded-xl border border-border bg-muted/40 p-3 font-mono text-sm break-all">
              {newKeyPlain}
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                if (newKeyPlain) {
                  navigator.clipboard
                    .writeText(newKeyPlain)
                    .then(() => toast("已複製部門金鑰", "success"))
                    .catch(() => {});
                }
              }}
            >
              複製
            </Button>
            <Button onClick={() => setNewKeyPlain(null)}>關閉</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ── 子元件:部門展開後的 SDK Keys 管理區塊 ──
function DepartmentKeysPanel({
  dept,
  keys,
  draft,
  setDraft,
  onAdd,
  adding,
  onToggle,
  onDelete,
  onCopy,
}: {
  dept: Department;
  keys: SdkKey[];
  draft: string;
  setDraft: (v: string) => void;
  onAdd: () => void;
  adding: boolean;
  onToggle: (k: SdkKey) => void;
  onDelete: (k: SdkKey) => void;
  onCopy: (k: SdkKey) => void;
}) {
  return (
    <div className="px-4 py-3 flex flex-col gap-3">
      {keys.length === 0 ? (
        <p className="text-sm text-muted-foreground">尚無金鑰,從下方建立第一把。</p>
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>名稱</TH>
              <TH>金鑰</TH>
              <TH>狀態</TH>
              <TH className="text-right">操作</TH>
            </TR>
          </THead>
          <TBody>
            {keys.map((k) => (
              <TR key={k.sdk_api_key_uid}>
                <TD className="whitespace-nowrap">{k.name}</TD>
                <TD>
                  {k.key_values ? (
                    <div className="flex items-center gap-1">
                      <code
                        className="font-mono text-sm text-muted-foreground truncate max-w-[260px]"
                        title={k.key_values}
                      >
                        {k.key_values}
                      </code>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="複製部門金鑰"
                        onClick={() => onCopy(k)}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                  ) : (
                    <span className="font-mono text-sm text-muted-foreground">
                      {k.key_prefix}··· (舊資料,請重新建立)
                    </span>
                  )}
                </TD>
                <TD>
                  <button
                    onClick={() => onToggle(k)}
                    className="hover:cursor-pointer"
                  >
                    <Badge variant={k.is_active ? "success" : "secondary"}>
                      {k.is_active ? "啟用" : "停用"}
                    </Badge>
                  </button>
                </TD>
                <TD className="text-right">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="刪除"
                    onClick={() => onDelete(k)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      <div className="flex items-center gap-2">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="新金鑰名稱(例:備援金鑰)"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !adding) onAdd();
          }}
          className="max-w-sm"
        />
        <LoadingButton
          variant="outline"
          onClick={onAdd}
          loading={adding}
        >
          <Plus className="h-4 w-4" />
          新增 SDK Key
        </LoadingButton>
      </div>
    </div>
  );
}
