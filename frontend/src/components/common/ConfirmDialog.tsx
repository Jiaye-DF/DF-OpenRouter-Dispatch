"use client";

import * as React from "react";
import { useDialog } from "@/lib/dialog";

// 封裝：呼叫 confirm 以 warning 樣式彈出雙按鈕對話框，Promise 化回傳結果
export function useConfirm() {
  const { showDialog, closeDialog } = useDialog();

  const confirm = React.useCallback(
    (opts: {
      title: string;
      message?: React.ReactNode;
      confirmText?: string;
      cancelText?: string;
      destructive?: boolean;
    }) => {
      return new Promise<boolean>((resolve) => {
        showDialog({
          type: "warning",
          title: opts.title,
          message: opts.message,
          confirmText: opts.confirmText ?? "確定",
          cancelText: opts.cancelText ?? "取消",
          destructive: opts.destructive ?? true,
          onConfirm: () => {
            resolve(true);
          },
          onCancel: () => {
            resolve(false);
            closeDialog();
          },
        });
      });
    },
    [showDialog, closeDialog]
  );

  return { confirm };
}
