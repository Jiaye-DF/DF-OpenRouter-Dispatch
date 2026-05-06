"use client";

import * as React from "react";
import { Palette } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
import { THEME_SERIES, type ThemeItem } from "@/lib/theme/themes";
import { useTheme } from "@/lib/theme/useTheme";

// 主題切換:Content Dialog(lg)+ 系列分區 + 卡片 grid + thumb 預覽
// 點卡片即時套用全頁;按「取消」回復 Dialog 開啟前主題;ESC / 遮罩 / X 僅關閉,保留當前選擇
export function ThemeSwitcher() {
  const [open, setOpen] = React.useState(false);
  const { current, applyTheme, revertTo } = useTheme();
  const originalRef = React.useRef<string>(current);

  React.useEffect(() => {
    if (open) {
      originalRef.current = current;
    }
    // 開啟瞬間擷取快照,刻意不依賴 current
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const handleCancel = () => {
    revertTo(originalRef.current);
    setOpen(false);
  };

  const handleDismiss = () => {
    setOpen(false);
  };

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        aria-label="切換主題"
        onClick={() => setOpen(true)}
      >
        <Palette className="h-5 w-5" />
      </Button>
      <Dialog open={open} onOpenChange={(o) => !o && handleDismiss()}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>選擇主題</DialogTitle>
          </DialogHeader>
          <div className="mt-4 flex max-h-[60vh] flex-col gap-6 overflow-auto pr-1">
            {THEME_SERIES.map((series) => (
              <section key={series.key} className="flex flex-col gap-3">
                <header className="flex items-baseline gap-2">
                  <h3 className="text-base font-semibold">{series.labelZh}</h3>
                  <span className="text-xs text-muted-foreground">
                    {series.labelEn}
                  </span>
                </header>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {series.items.map((item) => (
                    <ThemeCard
                      key={item.id}
                      item={item}
                      active={current === item.id}
                      onSelect={() => applyTheme(item.id)}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleCancel}>
              取消
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function ThemeCard({
  item,
  active,
  onSelect,
}: {
  item: ThemeItem;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={active}
      className={cn(
        "flex flex-col gap-2 rounded-xl border p-3 text-left transition-all hover:cursor-pointer hover:border-primary",
        active ? "border-primary ring-2 ring-primary" : "border-border"
      )}
    >
      <ThemeThumb colors={item.colors} />
      <div className="flex items-center gap-2">
        <span className="text-lg leading-none" aria-hidden>
          {item.icon}
        </span>
        <div className="flex flex-col">
          <span className="text-sm font-medium">{item.labelZh}</span>
          <span className="text-xs text-muted-foreground">{item.labelEn}</span>
        </div>
      </div>
    </button>
  );
}

function ThemeThumb({ colors }: { colors: ThemeItem["colors"] }) {
  return (
    <div
      className="flex h-16 w-full overflow-hidden rounded-lg border border-border"
      aria-hidden
    >
      <div
        className="flex flex-1 items-center justify-center text-xs font-medium"
        style={{ background: colors.background, color: colors.foreground }}
      >
        Aa
      </div>
      <div className="flex w-1/3 flex-col">
        <div className="flex-1" style={{ background: colors.primary }} />
        <div className="flex-1" style={{ background: colors.accent }} />
      </div>
    </div>
  );
}
