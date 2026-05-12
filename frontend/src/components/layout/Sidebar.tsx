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

// Sidebar：三狀態（expanded / collapsed / hidden），依角色顯示 nav 項目
interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "儀錶板", icon: LayoutDashboard },
  { href: "/departments", label: "部門", icon: Building2 },
  { href: "/projects", label: "專案", icon: FolderKanban },
  { href: "/users", label: "使用者", icon: Users, adminOnly: true },
  { href: "/admin/models", label: "模型管理", icon: Box, adminOnly: true },
  { href: "/admin/model-tiers", label: "模型分級", icon: Layers, adminOnly: true },
  {
    href: "/openrouter-keys",
    label: "OpenRouter Keys",
    icon: KeyRound,
    adminOnly: true,
  },
  { href: "/sdk-keys", label: "SDK Keys", icon: KeyRound, adminOnly: true },
  { href: "/usage-logs", label: "用量紀錄", icon: ScrollText },
  { href: "/user-guide", label: "使用者使用說明", icon: BookOpen },
];

export function Sidebar() {
  const pathname = usePathname();
  const state = useAppSelector((s) => s.theme.sidebarState);
  const actor = useAppSelector((s) => s.auth.actor);

  if (state === "hidden") return null;

  const collapsed = state === "collapsed";
  const role = actor?.role ?? "user";

  return (
    <aside
      className={cn(
        "sticky top-14 h-[calc(100vh-3.5rem)] border-r border-border bg-card text-card-foreground",
        "transition-[width] duration-200 ease-out",
        collapsed ? "w-16" : "w-60",
        "hidden md:block"
      )}
    >
      <nav className="py-4 px-2 flex flex-col gap-1">
        {NAV_ITEMS.filter((item) => !item.adminOnly || role === "admin").map(
          (item) => {
            const Icon = item.icon;
            const active =
              pathname === item.href || pathname?.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors",
                  "hover:bg-muted hover:cursor-pointer",
                  active && "bg-primary/10 text-primary font-medium",
                  collapsed && "justify-center"
                )}
              >
                <Icon className="h-5 w-5 shrink-0" />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </Link>
            );
          }
        )}
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
