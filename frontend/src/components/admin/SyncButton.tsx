"use client";

import * as React from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toaster";
import { useDialog } from "@/lib/dialog";
import { apiClient, ApiError } from "@/lib/api/client";
import type { ModelSyncResult, SyncThrottledData } from "@/types/api";

// 同步冷卻時間(秒);與後端 SYNC_THROTTLE_SECONDS 對齊(10 分鐘)
const COOLDOWN_SECONDS = 600;

interface SyncButtonProps {
  endpoint: string;
  onSuccess?: (data: ModelSyncResult) => void;
  // localStorage key 用於頁面切換後仍能持久顯示倒數
  storageKey?: string;
  className?: string;
}

function formatRemain(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

// 同步按鈕:
// - click 後立即 disabled + spinner,直到 API 回應
// - 成功 → Toast + 進入 cooldown 倒數 + localStorage 持久化
// - 425 sync_throttled → 依 retry_after_seconds 倒數
// - 其他失敗 → 顯示 detail
// - 進頁面時讀 localStorage 計算剩餘
export function SyncButton({
  endpoint,
  onSuccess,
  storageKey = "sync_models_last_ts",
  className,
}: SyncButtonProps) {
  const { toast } = useToast();
  const { showDialog } = useDialog();
  const [pending, setPending] = React.useState(false);
  const [remain, setRemain] = React.useState(0); // 秒;0 表示無冷卻
  const intervalRef = React.useRef<ReturnType<typeof setInterval> | null>(null);

  // 啟動倒數
  const startCountdown = React.useCallback((seconds: number) => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setRemain(seconds);
    intervalRef.current = setInterval(() => {
      setRemain((s) => {
        if (s <= 1) {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          return 0;
        }
        return s - 1;
      });
    }, 1000);
  }, []);

  // 進頁面時讀 localStorage 還原 cooldown(僅 mount 一次,避免 startCountdown 重生造成倒數重置)
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (raw) {
        const last = Number(raw);
        if (Number.isFinite(last)) {
          const elapsed = Math.floor((Date.now() - last) / 1000);
          if (elapsed >= 0 && elapsed < COOLDOWN_SECONDS) {
            startCountdown(COOLDOWN_SECONDS - elapsed);
          }
        }
      }
    } catch {
      // localStorage 取值失敗,忽略
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey]);

  const onClick = async () => {
    if (pending || remain > 0) return;
    setPending(true);
    try {
      const data = await apiClient.post<ModelSyncResult>(endpoint, {});
      try {
        window.localStorage.setItem(storageKey, String(Date.now()));
      } catch {
        // 寫入失敗不影響流程
      }
      startCountdown(COOLDOWN_SECONDS);
      toast(
        `同步成功:新增 ${data.added}、更新 ${data.updated}、停用 ${data.deactivated}、餘額同步 ${data.credits_synced}(失敗 ${data.credits_failed})`,
        "success"
      );
      onSuccess?.(data);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.detail === "sync_throttled") {
          const payload = err.data as SyncThrottledData | null;
          const retry =
            payload && typeof payload.retry_after_seconds === "number"
              ? Math.max(1, Math.floor(payload.retry_after_seconds))
              : COOLDOWN_SECONDS;
          startCountdown(retry);
          toast("同步冷卻中,稍後再試", "info");
        } else {
          showDialog({
            type: "error",
            title: "同步失敗",
            message: err.localizedDetail,
          });
        }
      } else {
        showDialog({
          type: "error",
          title: "同步失敗",
          message: "發生未預期錯誤,請稍後再試。",
        });
      }
    } finally {
      setPending(false);
    }
  };

  const disabled = pending || remain > 0;

  return (
    <Button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={className}
      aria-label="同步 OpenRouter 模型"
    >
      {pending ? (
        <Spinner size={16} />
      ) : (
        <RefreshCw className="h-4 w-4" />
      )}
      {remain > 0
        ? `同步冷卻中(剩餘 ${formatRemain(remain)})`
        : pending
        ? "同步中..."
        : "同步 OpenRouter"}
    </Button>
  );
}
