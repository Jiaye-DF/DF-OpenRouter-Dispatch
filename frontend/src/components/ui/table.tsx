import * as React from "react";
import { cn } from "@/lib/utils/cn";

// 輕量 Table 元件：封裝一致的間距與 border

export function Table({
  className,
  ...props
}: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="w-full overflow-x-auto">
      <table
        className={cn("w-full text-sm border-collapse", className)}
        {...props}
      />
    </div>
  );
}

export function THead({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead
      className={cn("bg-muted/60 text-muted-foreground", className)}
      {...props}
    />
  );
}

export function TBody({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn("", className)} {...props} />;
}

export function TR({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn(
        "border-b border-border last:border-0 hover:bg-muted/40 transition-colors",
        className
      )}
      {...props}
    />
  );
}

export function TH({
  className,
  ...props
}: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        "text-left font-medium px-4 py-3 text-sm uppercase tracking-wide whitespace-nowrap",
        className
      )}
      {...props}
    />
  );
}

export function TD({
  className,
  ...props
}: React.TdHTMLAttributes<HTMLTableCellElement>) {
  // whitespace-nowrap：避免長文字擠壓欄位，過長時由 Table 外層水平捲動
  return (
    <td
      className={cn("px-4 py-3 align-middle whitespace-nowrap", className)}
      {...props}
    />
  );
}
