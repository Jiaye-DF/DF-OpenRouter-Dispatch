"use client";

import * as React from "react";
import { cn } from "@/lib/utils/cn";

// 手刻 shadcn 風格 Switch:滑軌 + 圓形滑塊,checked 以 bg-primary 標示
// role="switch" + aria-checked;原生 button 承載鍵盤操作與 focus ring
// 觸控目標:視覺軌道 24px 高,以 after 偽元素撐大點擊區至 ≥44px(對齊 06-rwd.md)

export interface SwitchProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onChange"> {
  checked: boolean;
  onCheckedChange?: (checked: boolean) => void;
}

export const Switch = React.forwardRef<HTMLButtonElement, SwitchProps>(
  ({ className, checked, onCheckedChange, onClick, ...props }, ref) => {
    return (
      <button
        ref={ref}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={(e) => {
          onClick?.(e);
          if (!e.defaultPrevented) onCheckedChange?.(!checked);
        }}
        className={cn(
          "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors",
          "after:absolute after:-inset-2.5 after:content-['']",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50",
          "disabled:opacity-50 disabled:pointer-events-none hover:cursor-pointer",
          checked ? "bg-primary border-primary" : "bg-muted border-border",
          className
        )}
        {...props}
      >
        <span
          aria-hidden="true"
          className={cn(
            "pointer-events-none block h-5 w-5 rounded-full bg-background shadow-sm transition-transform",
            checked ? "translate-x-5" : "translate-x-0.5"
          )}
        />
      </button>
    );
  }
);
Switch.displayName = "Switch";
