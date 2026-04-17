"use client";

import * as React from "react";
import { AlertTriangle, Info, XCircle } from "lucide-react";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";

// 全域 Dialog 提供者：類型分 Info / Warning / Error，搭配 lucide 圖示
export type DialogType = "info" | "warning" | "error";

export interface DialogOptions {
  type?: DialogType;
  title: string;
  message?: React.ReactNode;
  confirmText?: string;
  cancelText?: string;
  onConfirm?: () => void | Promise<void>;
  onCancel?: () => void;
  // 為 warning 指定 true 時顯示「取消/確定」雙鈕，且確定為危險色
  destructive?: boolean;
}

interface DialogState extends DialogOptions {
  open: boolean;
  pending: boolean;
}

interface DialogContextValue {
  showDialog: (opts: DialogOptions) => void;
  closeDialog: () => void;
}

const DialogContext = React.createContext<DialogContextValue | null>(null);

export function DialogProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<DialogState>({
    open: false,
    pending: false,
    title: "",
    type: "info",
  });

  const showDialog = React.useCallback((opts: DialogOptions) => {
    setState({
      open: true,
      pending: false,
      type: opts.type ?? "info",
      title: opts.title,
      message: opts.message,
      confirmText: opts.confirmText,
      cancelText: opts.cancelText,
      onConfirm: opts.onConfirm,
      onCancel: opts.onCancel,
      destructive: opts.destructive,
    });
  }, []);

  const closeDialog = React.useCallback(() => {
    setState((s) => ({ ...s, open: false }));
  }, []);

  const handleConfirm = async () => {
    try {
      setState((s) => ({ ...s, pending: true }));
      await state.onConfirm?.();
      setState((s) => ({ ...s, open: false, pending: false }));
    } catch {
      setState((s) => ({ ...s, pending: false }));
    }
  };

  const handleCancel = () => {
    state.onCancel?.();
    closeDialog();
  };

  const icon = React.useMemo(() => {
    const cls = "h-6 w-6 shrink-0";
    switch (state.type) {
      case "warning":
        return <AlertTriangle className={cn(cls, "text-amber-500")} />;
      case "error":
        return <XCircle className={cn(cls, "text-red-500")} />;
      default:
        return <Info className={cn(cls, "text-blue-500")} />;
    }
  }, [state.type]);

  const showCancel =
    state.destructive === true ||
    state.type === "warning" ||
    !!state.cancelText;

  return (
    <DialogContext.Provider value={{ showDialog, closeDialog }}>
      {children}
      <Dialog open={state.open} onOpenChange={(o) => !o && closeDialog()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-3">
              {icon}
              <span>{state.title}</span>
            </DialogTitle>
          </DialogHeader>
          {state.message && (
            <div className="text-sm text-foreground/80 leading-relaxed pt-1">
              {state.message}
            </div>
          )}
          <DialogFooter>
            {showCancel && (
              <Button
                type="button"
                variant="outline"
                onClick={handleCancel}
                disabled={state.pending}
              >
                {state.cancelText ?? "取消"}
              </Button>
            )}
            <Button
              type="button"
              variant={state.destructive ? "destructive" : "default"}
              onClick={handleConfirm}
              disabled={state.pending}
            >
              {state.confirmText ?? "確認"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DialogContext.Provider>
  );
}

export function useDialog(): DialogContextValue {
  const ctx = React.useContext(DialogContext);
  if (!ctx) throw new Error("useDialog 必須在 <DialogProvider> 之內使用");
  return ctx;
}
