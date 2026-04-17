"use client";

import * as React from "react";
import { cn } from "@/lib/utils/cn";

// 極簡 Toast：僅用於成功 / 一般訊息；錯誤 / 警告一律走 Dialog

type ToastType = "info" | "success" | "error";

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
}

interface ToasterContextValue {
  toast: (message: string, type?: ToastType) => void;
}

const ToasterCtx = React.createContext<ToasterContextValue | null>(null);

export function ToasterProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = React.useState<Toast[]>([]);

  const toast = React.useCallback((message: string, type: ToastType = "info") => {
    const id = Math.random().toString(36).slice(2);
    setItems((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setItems((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  }, []);

  return (
    <ToasterCtx.Provider value={{ toast }}>
      {children}
      <div className="fixed top-4 right-4 z-[200] flex flex-col gap-2 pointer-events-none">
        {items.map((t) => (
          <div
            key={t.id}
            className={cn(
              "pointer-events-auto rounded-xl border px-4 py-3 text-sm shadow-md bg-card text-card-foreground animate-fade-in",
              t.type === "success" && "border-emerald-500/40",
              t.type === "error" && "border-destructive/40",
              t.type === "info" && "border-border"
            )}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToasterCtx.Provider>
  );
}

export function useToast() {
  const ctx = React.useContext(ToasterCtx);
  if (!ctx) throw new Error("useToast 必須在 <ToasterProvider> 之內使用");
  return ctx;
}
