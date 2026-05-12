"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  BookOpen,
  Box,
  Building2,
  FolderKanban,
  KeyRound,
  Layers,
  LayoutDashboard,
  ScrollText,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useAppSelector } from "@/store/hooks";

// Sidebar:三狀態(expanded / collapsed / hidden);依角色顯示;按主題分組
interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  adminOnly?: boolean;
}

interface NavSection {
  label?: string; // 若 omit 視為「概覽」(無標題)
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    items: [
      { href: "/dashboard", label: "儀錶板", icon: LayoutDashboard },
      { href: "/usage-logs", label: "用量紀錄", icon: ScrollText },
    ],
  },
  {
    label: "組織",
    items: [
      { href: "/departments", label: "部門", icon: Building2 },
      { href: "/projects", label: "專案", icon: FolderKanban },
      { href: "/users", label: "使用者", icon: Users, adminOnly: true },
    ],
  },
  {
    label: "模型",
    items: [
      { href: "/admin/models", label: "模型管理", icon: Box, adminOnly: true },
      {
        href: "/admin/model-tiers",
        label: "模型分級",
        icon: Layers,
        adminOnly: true,
      },
    ],
  },
  {
    label: "金鑰",
    items: [
      {
        href: "/openrouter-keys",
        label: "OpenRouter Keys",
        icon: KeyRound,
        adminOnly: true,
      },
      {
        href: "/internal-keys",
        label: "Internal Keys",
        icon: KeyRound,
        adminOnly: true,
      },
      { href: "/sdk-keys", label: "SDK Keys", icon: KeyRound, adminOnly: true },
    ],
  },
  {
    label: "說明",
    items: [{ href: "/user-guide", label: "使用者使用說明", icon: BookOpen }],
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
                <div className="px-3 pt-4 pb-1 text-xs font-medium tracking-wider text-muted-foreground/70 uppercase">
                  {sec.label ?? ""}
                </div>
              ))}
            {!collapsed && idx === 0 && sec.label && (
              <div className="px-3 pb-1 text-xs font-medium tracking-wider text-muted-foreground/70 uppercase">
                {sec.label}
              </div>
            )}
            <div className="flex flex-col gap-1">
              {sec.items.map((item) => {
                const Icon = item.icon;
                const active =
                  pathname === item.href ||
                  pathname?.startsWith(`${item.href}/`);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    title={collapsed ? item.label : undefined}
                    className={cn(
                      "flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors",
                      "hover:bg-muted hover:cursor-pointer",
                      active && "bg-primary/10 text-primary font-medium",
                      collapsed && "justify-center"
                    )}
                  >
                    <Icon className="h-5 w-5 shrink-0" />
                    {!collapsed && (
                      <span className="truncate">{item.label}</span>
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
            {!collapsed && <span>一般使用者檢視</span>}
          </div>
        )}
      </nav>
    </aside>
  );
}
