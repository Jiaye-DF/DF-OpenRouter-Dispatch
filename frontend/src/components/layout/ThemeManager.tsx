"use client";

import * as React from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { setTheme, type ThemeName } from "@/store/theme-slice";

const VALID: ThemeName[] = ["light", "dark", "cool", "warm", "purple"];

// 主題管理：開機讀 localStorage、每次 theme 變動同步至 <html> class 與 data-theme
export function ThemeManager() {
  const dispatch = useAppDispatch();
  const theme = useAppSelector((s) => s.theme.theme);
  const mounted = React.useRef(false);

  // 初次掛載：從 localStorage 讀取偏好（若無則依系統 prefers-color-scheme 擇 light/dark）
  React.useEffect(() => {
    if (mounted.current) return;
    mounted.current = true;
    try {
      const stored = localStorage.getItem("theme") as ThemeName | null;
      if (stored && VALID.includes(stored)) {
        dispatch(setTheme(stored));
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

  // 同步到 <html>：class="dark" / data-theme="cool|warm|purple"
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
