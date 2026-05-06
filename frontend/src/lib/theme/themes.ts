// 佈景主題資料(Series + Theme 兩層結構)
// 對齊 docs/Design-Base/11-ui-ux.md「光影 Atmosphere」系列;id 沿用舊值避免 localStorage 遷移

export const THEME_STORAGE_KEY = "agents-platform-theme";
export const LEGACY_THEME_STORAGE_KEY = "theme";

export type ThemeId = "light" | "dark" | "cool" | "warm" | "purple";

export interface ThemeColors {
  background: string;
  foreground: string;
  primary: string;
  accent: string;
}

export interface ThemeItem {
  id: string;
  labelZh: string;
  labelEn: string;
  icon: string;
  colors: ThemeColors;
  source: "builtin" | "user";
}

export interface ThemeSeries {
  key: string;
  labelZh: string;
  labelEn: string;
  source: "builtin" | "user";
  items: ThemeItem[];
}

const ATMOSPHERE_ITEMS: ThemeItem[] = [
  {
    id: "light",
    labelZh: "晨曦",
    labelEn: "Dawn",
    icon: "◐",
    colors: {
      background: "#ffffff",
      foreground: "#171717",
      primary: "#2563eb",
      accent: "#3b82f6",
    },
    source: "builtin",
  },
  {
    id: "cool",
    labelZh: "霧境",
    labelEn: "Nordic",
    icon: "❅",
    colors: {
      background: "#f0f4f8",
      foreground: "#1e293b",
      primary: "#0ea5e9",
      accent: "#06b6d4",
    },
    source: "builtin",
  },
  {
    id: "warm",
    labelZh: "夕映",
    labelEn: "Ember",
    icon: "◉",
    colors: {
      background: "#fdf6ec",
      foreground: "#44403c",
      primary: "#ea580c",
      accent: "#f59e0b",
    },
    source: "builtin",
  },
  {
    id: "purple",
    labelZh: "暮霞",
    labelEn: "Twilight",
    icon: "✦",
    colors: {
      background: "#faf5ff",
      foreground: "#3b0764",
      primary: "#a855f7",
      accent: "#e879f9",
    },
    source: "builtin",
  },
  {
    id: "dark",
    labelZh: "深夜",
    labelEn: "Midnight",
    icon: "☾",
    colors: {
      background: "#0a0a0a",
      foreground: "#ededed",
      primary: "#60a5fa",
      accent: "#93c5fd",
    },
    source: "builtin",
  },
];

export const THEME_SERIES: ThemeSeries[] = [
  {
    key: "atmosphere",
    labelZh: "光影",
    labelEn: "Atmosphere",
    source: "builtin",
    items: ATMOSPHERE_ITEMS,
  },
];

export const ALL_THEME_IDS: ThemeId[] = ATMOSPHERE_ITEMS.map(
  (i) => i.id as ThemeId
);

export function isValidThemeId(id: string): id is ThemeId {
  return (ALL_THEME_IDS as string[]).includes(id);
}

export function findThemeItem(id: string): ThemeItem | undefined {
  for (const series of THEME_SERIES) {
    const item = series.items.find((i) => i.id === id);
    if (item) return item;
  }
  return undefined;
}
