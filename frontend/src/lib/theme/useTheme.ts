"use client";

import * as React from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { setTheme, type ThemeName } from "@/store/theme-slice";
import {
  THEME_STORAGE_KEY,
  findThemeItem,
  isValidThemeId,
} from "@/lib/theme/themes";

// applyTheme:即時套用並寫入 localStorage(Switcher 點卡即用)
// revertTo:取消時回復到 Dialog 開啟前的主題,並覆寫 localStorage(避免 reload 後保留中途試選)
export function useTheme() {
  const dispatch = useAppDispatch();
  const current = useAppSelector((s) => s.theme.theme);

  const writeAndSet = React.useCallback(
    (id: string) => {
      if (!isValidThemeId(id)) return;
      if (!findThemeItem(id)) return;
      dispatch(setTheme(id as ThemeName));
      try {
        localStorage.setItem(THEME_STORAGE_KEY, id);
      } catch {
        // 忽略 storage 不可用
      }
    },
    [dispatch]
  );

  return {
    current,
    applyTheme: writeAndSet,
    revertTo: writeAndSet,
  };
}
