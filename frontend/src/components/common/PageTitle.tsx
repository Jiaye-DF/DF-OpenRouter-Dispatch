import * as React from "react";
import { cn } from "@/lib/utils/cn";

interface PageTitleProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}

// 統一頁面標題區塊：title + 可選描述 + 右側操作
export function PageTitle({
  title,
  description,
  actions,
  className,
}: PageTitleProps) {
  return (
    <div
      className={cn(
        "mb-6 flex flex-col gap-2 md:flex-row md:items-center md:justify-between",
        className
      )}
    >
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="text-sm text-muted-foreground mt-1">{description}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
