"use client";

import * as React from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { setTheme, type ThemeName } from "@/store/theme-slice";
import {
  ALL_THEME_IDS,
  LEGACY_THEME_STORAGE_KEY,
  THEME_STORAGE_KEY,
} from "@/lib/theme/themes";

// 主題管理:開機讀 localStorage(含舊 key 一次性遷移)、每次 theme 變動同步至 <html>
export function ThemeManager() {
  const dispatch = useAppDispatch();
  const theme = useAppSelector((s) => s.theme.theme);
  const mounted = React.useRef(false);

  React.useEffect(() => {
    if (mounted.current) return;
    mounted.current = true;
    try {
      const stored = localStorage.getItem(THEME_STORAGE_KEY) as
        | ThemeName
        | null;
      if (stored && (ALL_THEME_IDS as string[]).includes(stored)) {
        dispatch(setTheme(stored));
        return;
      }
      // 一次性遷移:舊版本以 'theme' 為 key
      const legacy = localStorage.getItem(LEGACY_THEME_STORAGE_KEY) as
        | ThemeName
        | null;
      if (legacy && (ALL_THEME_IDS as string[]).includes(legacy)) {
        localStorage.setItem(THEME_STORAGE_KEY, legacy);
        localStorage.removeItem(LEGACY_THEME_STORAGE_KEY);
        dispatch(setTheme(legacy));
        return;
      }
    } catch {
      // 忽略 storage 不可用
    }
    if (typeof window !== "undefined" && window.matchMedia) {
      const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      dispatch(setTheme(isDark ? "dark" : "light"));
    }
  }, [dispatch]);

  React.useEffect(() => {
    if (typeof document === "undefined") return;
    const html = document.documentElement;
    html.classList.toggle("dark", theme === "dark");
    if (theme === "light" || theme === "dark") {
      html.removeAttribute("data-theme");
    } else {
      html.setAttribute("data-theme", theme);
    }
  }, [theme]);

  return null;
}
