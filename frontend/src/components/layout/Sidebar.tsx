"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  BookOpen,
  Box,
  Building2,
  CheckSquare,
  Cloud,
  FolderKanban,
  KeyRound,
  Layers,
  LayoutDashboard,
  ScrollText,
  ShieldCheck,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useAppSelector } from "@/store/hooks";

// Sidebar 三狀態(expanded / collapsed / hidden);依角色顯示;按主題分組
// 金鑰刻意拆「對外呼叫(平台→模型)」與「對內接受(SDK→平台)」兩個 section,
// 區分方向,避免新人把三種 Key 看成同一類東西
interface NavItem {
  href: string;
  label: string;
  subtitle?: string; // 副標(expanded 時顯示小字;collapsed 時併入 tooltip)
  icon: React.ComponentType<{ className?: string }>;
  adminOnly?: boolean;
}

interface NavSection {
  label?: string; // 若 omit 視為「概覽」(無標題)
  hint?: string; // section 副標(grouping 用途說明)
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    items: [
      { href: "/dashboard", label: "儀錶板", icon: LayoutDashboard },
      { href: "/api-key-requests", label: "API Key 申請表單", icon: KeyRound },
      { href: "/usage-logs", label: "用量紀錄", icon: ScrollText, adminOnly: true },
    ],
  },
  {
    label: "組織",
    items: [
      { href: "/departments", label: "部門", icon: Building2, adminOnly: true },
      { href: "/projects", label: "專案", icon: FolderKanban, adminOnly: true },
      { href: "/users", label: "使用者", icon: Users, adminOnly: true },
    ],
  },
  {
    label: "模型",
    items: [
      { href: "/admin/models", label: "模型管理", icon: Box, adminOnly: true },
      {
        href: "/admin/allowed-models",
        label: "模型白名單",
        icon: CheckSquare,
        adminOnly: true,
      },
      {
        href: "/admin/model-tiers",
        label: "模型分級",
        icon: Layers,
        adminOnly: true,
      },
    ],
  },
  {
    label: "模型來源金鑰",
    hint: "對外呼叫 · 平台→模型",
    items: [
      {
        href: "/openrouter-keys",
        label: "OpenRouter Keys",
        subtitle: "雲端 · OpenRouter",
        icon: Cloud,
        adminOnly: true,
      },
      // 本地模型功能暫時停用 — 暫不顯示 Internal Keys 入口(待實際導入企業內部模型再開啟)
      // {
      //   href: "/internal-keys",
      //   label: "Internal Keys",
      //   subtitle: "地端 · OpenAI-compatible",
      //   icon: Server,
      //   adminOnly: true,
      // },
    ],
  },
  // v1.6:「存取金鑰」section 已併入「部門」頁(部門 row 可展開管 SDK Keys),
  // 此處不再單獨列出;舊書籤直打 /sdk-keys 仍可進得去。
  {
    label: "說明",
    items: [
      { href: "/user-guide", label: "使用者使用說明", icon: BookOpen },
      {
        href: "/admin-guide",
        label: "管理者使用說明",
        icon: ShieldCheck,
        adminOnly: true,
      },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const state = useAppSelector((s) => s.theme.sidebarState);
  const actor = useAppSelector((s) => s.auth.actor);

  if (state === "hidden") return null;

  const collapsed = state === "collapsed";
  const role = actor?.role ?? "user";

  // 過濾掉 adminOnly 與空 section
  const visibleSections = NAV_SECTIONS.map((sec) => ({
    ...sec,
    items: sec.items.filter((it) => !it.adminOnly || role === "admin"),
  })).filter((sec) => sec.items.length > 0);

  return (
    <aside
      className={cn(
        "sticky top-14 h-[calc(100vh-3.5rem)] border-r border-border bg-card text-card-foreground",
        "transition-[width] duration-200 ease-out overflow-y-auto",
        collapsed ? "w-16" : "w-60",
        "hidden md:block"
      )}
    >
      <nav className="py-4 px-2 flex flex-col">
        {visibleSections.map((sec, idx) => (
          <React.Fragment key={sec.label ?? `__sec_${idx}`}>
            {idx > 0 &&
              (collapsed ? (
                <div className="mx-2 my-2 h-px bg-border" aria-hidden />
              ) : (
                <div className="px-3 pt-4 pb-1">
                  <div className="text-sm font-medium tracking-wider text-muted-foreground/70 uppercase">
                    {sec.label ?? ""}
                  </div>
                  {sec.hint && (
                    <div className="text-sm text-muted-foreground/60 mt-0.5">
                      {sec.hint}
                    </div>
                  )}
                </div>
              ))}
            {!collapsed && idx === 0 && sec.label && (
              <div className="px-3 pb-1">
                <div className="text-sm font-medium tracking-wider text-muted-foreground/70 uppercase">
                  {sec.label}
                </div>
                {sec.hint && (
                  <div className="text-sm text-muted-foreground/60 mt-0.5">
                    {sec.hint}
                  </div>
                )}
              </div>
            )}
            <div className="flex flex-col gap-1">
              {sec.items.map((item) => {
                const Icon = item.icon;
                const active =
                  pathname === item.href ||
                  pathname?.startsWith(`${item.href}/`);
                const tooltip = collapsed
                  ? item.subtitle
                    ? `${item.label} · ${item.subtitle}`
                    : item.label
                  : undefined;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    title={tooltip}
                    className={cn(
                      "flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors",
                      "hover:bg-muted hover:cursor-pointer",
                      active && "bg-primary/10 text-primary font-medium",
                      collapsed && "justify-center"
                    )}
                  >
                    <Icon className="h-5 w-5 shrink-0" />
                    {!collapsed && (
                      <div className="min-w-0 flex-1">
                        <div className="truncate">{item.label}</div>
                        {item.subtitle && (
                          <div className="truncate text-sm text-muted-foreground/70 leading-tight">
                            {item.subtitle}
                          </div>
                        )}
                      </div>
                    )}
                  </Link>
                );
              })}
            </div>
          </React.Fragment>
        ))}

        {role !== "admin" && (
          <div
            className={cn(
              "mt-auto pt-4 pb-2 flex items-center gap-2 text-sm text-muted-foreground",
              collapsed ? "justify-center" : "px-3"
            )}
          >
            <BarChart3 className="h-3.5 w-3.5" />
            {!collapsed && <span>成員檢視</span>}
          </div>
        )}
      </nav>
    </aside>
  );
}
