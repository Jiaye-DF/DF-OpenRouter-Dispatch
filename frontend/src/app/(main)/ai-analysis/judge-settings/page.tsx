"use client";

import * as React from "react";
import { Brain, Save } from "lucide-react";
import { PageTitle } from "@/components/common/PageTitle";
import { PageHint } from "@/components/common/PageHint";
import { Card, CardContent } from "@/components/ui/card";
import { LoadingButton } from "@/components/common/LoadingButton";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { Combobox, type ComboboxOption } from "@/components/ui/Combobox";
import { useDialog } from "@/lib/dialog";
import { useToast } from "@/components/ui/toaster";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import type { JudgeSetting, Model, Paginated } from "@/types/api";
import { useAppSelector } from "@/store/hooks";

const SLOT_COUNT = 3;
const SLOT_LABELS = ["模型設定 1", "模型設定 2", "模型設定 3"] as const;

export default function JudgeSettingsPage() {
  const role = useAppSelector((s) => s.auth.actor?.role);
  const { showDialog } = useDialog();
  const { toast } = useToast();

  const [models, setModels] = React.useState<Model[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);

  // 3 個槽位選中的 model_uid(空字串代表未選)
  const [slots, setSlots] = React.useState<string[]>(["", "", ""]);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      // 模型清單沿用既有 models 端點;後端一次回傳全部,前端只取 active
      const [list, settings] = await Promise.all([
        apiClient.get<Paginated<Model>>(API_ENDPOINTS.models, {
          query: { include_inactive: 1 },
        }),
        apiClient.get<JudgeSetting[]>(API_ENDPOINTS.aiEvalJudgeSettings),
      ]);
      setModels(list.items.filter((m) => m.is_active));

      // 依 slot 1→3 回填現有設定;未設定時 3 個槽位留空
      const next = ["", "", ""];
      for (const s of settings ?? []) {
        const idx = s.ai_judge_slot - 1;
        if (idx >= 0 && idx < SLOT_COUNT) next[idx] = s.model_uid;
      }
      setSlots(next);
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

  // 各槽位的 Combobox 選項:排除「其他槽位已選」的模型(UI 阻擋重複)。
  // 自身已選的模型仍保留,確保 trigger 能顯示當前選項。
  const optionsForSlot = React.useCallback(
    (slotIdx: number): ComboboxOption[] => {
      const takenByOthers = new Set(
        slots.filter((_, i) => i !== slotIdx && slots[i] !== "")
      );
      return [...models]
        .filter((m) => !takenByOthers.has(m.model_uid))
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((m) => ({
          value: m.model_uid,
          label: `${m.name}(${m.model_key})`,
        }));
    },
    [models, slots]
  );

  const setSlot = (slotIdx: number, value: string) => {
    setSlots((prev) => {
      const next = [...prev];
      next[slotIdx] = value;
      return next;
    });
  };

  const filledCount = slots.filter((s) => s !== "").length;
  const hasDuplicate =
    new Set(slots.filter((s) => s !== "")).size !==
    slots.filter((s) => s !== "").length;
  const canSave = filledCount === SLOT_COUNT && !hasDuplicate;

  const onSave = async () => {
    if (!canSave) {
      showDialog({
        type: "warning",
        title: "尚未完成設定",
        message: hasDuplicate
          ? "判別模型不可重複,請改選不同的模型。"
          : "請正好選擇 3 個判別模型。",
      });
      return;
    }
    setSaving(true);
    try {
      const updated = await apiClient.put<JudgeSetting[]>(
        API_ENDPOINTS.aiEvalJudgeSettings,
        { model_uids: slots }
      );
      // 以回傳結果重新回填,確保與後端一致(slot 順序由後端決定)
      const next = ["", "", ""];
      for (const s of updated ?? []) {
        const idx = s.ai_judge_slot - 1;
        if (idx >= 0 && idx < SLOT_COUNT) next[idx] = s.model_uid;
      }
      setSlots(next);
      toast("判別模型已儲存", "success");
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

  if (role !== "admin") {
    return (
      <>
        <PageTitle title="設定判別模型" />
        <Card>
          <CardContent className="pt-6">
            <EmptyState title="權限不足" description="本頁僅限 admin 存取" />
          </CardContent>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageTitle
        title="設定判別模型"
        description="設定 AI 分析使用的判別模型(恰 3 個,不可重複)"
      />
      <PageHint title="設定判別模型做什麼用的?">
        指定 3 個模型當「模型分析」的評審;系統用它們交叉評審用量紀錄,判斷原模型是否適配並推薦更合適者。從 active 模型挑 3 個,建議跨廠商以抵銷偏好偏差。
      </PageHint>

      <Card>
        <CardContent className="pt-6 flex flex-col gap-6">
          {loading ? (
            <div className="flex flex-col gap-4">
              {Array.from({ length: SLOT_COUNT }).map((_, i) => (
                <div
                  key={i}
                  className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4"
                >
                  <Skeleton className="h-4 w-32 shrink-0" />
                  <Skeleton className="h-9 w-full sm:w-96" />
                </div>
              ))}
            </div>
          ) : models.length === 0 ? (
            <EmptyState
              title="尚無可用模型"
              description="請先到「模型管理」啟用至少 3 個模型,再回此頁設定判別模型。"
            />
          ) : (
            <>
              <div className="flex flex-col gap-4">
                {SLOT_LABELS.map((label, idx) => {
                  const Icon = Brain;
                  return (
                    <div
                      key={idx}
                      className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4"
                    >
                      <span className="flex w-40 shrink-0 items-center gap-2 text-sm font-medium">
                        <Icon className="h-4 w-4 text-muted-foreground" />
                        {label}
                      </span>
                      <Combobox
                        className="w-full sm:w-96"
                        options={optionsForSlot(idx)}
                        value={slots[idx]}
                        onChange={(v) => setSlot(idx, v)}
                        placeholder="選擇模型..."
                        searchPlaceholder="輸入模型名稱..."
                        emptyText="查無可選模型"
                      />
                    </div>
                  );
                })}
              </div>

              <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  {hasDuplicate && (
                    <p className="text-sm text-destructive">
                      判別模型不可重複,請改選不同的模型。
                    </p>
                  )}
                </div>
                <LoadingButton
                  onClick={onSave}
                  loading={saving}
                  disabled={!canSave}
                  className="shrink-0"
                >
                  <Save className="h-4 w-4" />
                  儲存
                </LoadingButton>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </>
  );
}
