"use client";

import * as React from "react";
import { cn } from "@/lib/utils/cn";

// 篩選 chip:小圓角、單選切換、active 以 bg-primary 實心背景標示
// 對齊 docs/Design-Base/11-ui-ux.md § 篩選與排序 chip

interface FilterChipProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
}

export function FilterChip({
  active,
  className,
  children,
  ...props
}: FilterChipProps) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cn(
        "inline-flex items-center justify-center rounded-full border px-3 py-1 text-xs font-medium transition-colors hover:cursor-pointer",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50",
        active
          ? "bg-primary text-primary-foreground border-primary"
          : "bg-transparent text-foreground border-border hover:bg-muted",
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
