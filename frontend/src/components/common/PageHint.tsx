import * as React from "react";
import { Info, AlertTriangle, Lightbulb } from "lucide-react";
import { cn } from "@/lib/utils/cn";

type Tone = "info" | "warning" | "tip";

interface PageHintProps {
  tone?: Tone;
  title?: string;
  children: React.ReactNode;
  className?: string;
}

const TONE_STYLES: Record<Tone, { wrap: string; icon: React.ReactNode }> = {
  info: {
    wrap: "border-blue-500/30 bg-blue-500/5",
    icon: <Info className="h-5 w-5 text-blue-600 shrink-0 mt-0.5" />,
  },
  warning: {
    wrap: "border-amber-500/30 bg-amber-500/5",
    icon: <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />,
  },
  tip: {
    wrap: "border-emerald-500/30 bg-emerald-500/5",
    icon: <Lightbulb className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />,
  },
};

// 頁面提示橫幅:用於頁頂解釋業務語意 / 注意事項 / 操作建議
// 三種 tone:info(藍·說明)、warning(琥珀·注意)、tip(綠·建議)
export function PageHint({
  tone = "info",
  title,
  children,
  className,
}: PageHintProps) {
  const { wrap, icon } = TONE_STYLES[tone];
  return (
    <div
      className={cn(
        "rounded-xl border px-4 py-3 mb-4 flex gap-3 text-sm",
        wrap,
        className
      )}
    >
      {icon}
      <div className="flex flex-col gap-1 leading-relaxed flex-1 min-w-0">
        {title && <div className="font-medium">{title}</div>}
        <div className="text-foreground/85">{children}</div>
      </div>
    </div>
  );
}
