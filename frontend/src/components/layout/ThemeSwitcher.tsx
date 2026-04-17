"use client";

import * as React from "react";
import { Palette } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { setTheme, type ThemeName } from "@/store/theme-slice";

// 主題切換 Popover：列出五套主題（淺色 / 深色 / 冷色 / 暖色 / 粉紫）

const themes: { value: ThemeName; label: string }[] = [
  { value: "light", label: "淺色" },
  { value: "dark", label: "深色" },
  { value: "cool", label: "冷色系" },
  { value: "warm", label: "暖色系" },
  { value: "purple", label: "粉紫色" },
];

export function ThemeSwitcher() {
  const [open, setOpen] = React.useState(false);
  const dispatch = useAppDispatch();
  const current = useAppSelector((s) => s.theme.theme);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  const pick = (t: ThemeName) => {
    dispatch(setTheme(t));
    try {
      localStorage.setItem("theme", t);
    } catch {
      // SSR 或無權存取時忽略
    }
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative">
      <Button
        variant="ghost"
        size="icon"
        aria-label="切換主題"
        onClick={() => setOpen((o) => !o)}
      >
        <Palette className="h-5 w-5" />
      </Button>
      {open && (
        <div className="absolute right-0 mt-2 w-40 rounded-xl border border-border bg-card text-card-foreground shadow-lg z-50 animate-fade-in overflow-hidden">
          {themes.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => pick(t.value)}
              className={cn(
                "w-full text-left px-4 py-2 text-sm hover:bg-muted hover:cursor-pointer",
                current === t.value && "bg-muted font-medium"
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
