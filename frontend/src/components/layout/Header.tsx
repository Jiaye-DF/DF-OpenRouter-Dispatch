"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut, Menu, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { apiClient } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { clearAuth } from "@/store/auth-slice";
import { cycleSidebarState } from "@/store/theme-slice";
import { cn } from "@/lib/utils/cn";

// Header：左 Sidebar 切換 + Logo，右 主題切換 + 使用者資訊 + 登出
export function Header() {
  const dispatch = useAppDispatch();
  const router = useRouter();
  const actor = useAppSelector((s) => s.auth.actor);
  const [popoverOpen, setPopoverOpen] = React.useState(false);
  const popRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (popRef.current && !popRef.current.contains(e.target as Node)) {
        setPopoverOpen(false);
      }
    };
    if (popoverOpen) document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [popoverOpen]);

  const handleLogout = async () => {
    try {
      await apiClient.post(API_ENDPOINTS.logout, {});
    } catch {
      // best-effort：即使失敗也強制清除本地狀態
    }
    dispatch(clearAuth());
    router.push("/login");
  };

  return (
    <header
      className={cn(
        "sticky top-0 z-50 h-14 border-b border-border",
        "bg-card text-card-foreground",
        "flex items-center justify-between px-4 md:px-6"
      )}
    >
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          aria-label="切換選單"
          onClick={() => dispatch(cycleSidebarState())}
        >
          <Menu className="h-5 w-5" />
        </Button>
        <Link
          href="/dashboard"
          className="flex items-center gap-2 hover:cursor-pointer"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Zap className="h-4 w-4" />
          </div>
          <span className="hidden sm:inline font-semibold tracking-tight">
            Model Dispatcher
          </span>
        </Link>
      </div>

      <div className="flex items-center gap-2">
        <ThemeSwitcher />
        {actor ? (
          <div ref={popRef} className="relative">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPopoverOpen((o) => !o)}
              className="gap-2"
            >
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-primary/15 text-primary text-sm font-medium">
                {actor.username?.slice(0, 1) ?? "?"}
              </span>
              <span className="hidden md:inline">{actor.username}</span>
            </Button>
            {popoverOpen && (
              <div className="absolute right-0 mt-2 w-64 rounded-xl border border-border bg-card text-card-foreground shadow-lg z-50 animate-fade-in overflow-hidden">
                <div className="px-4 py-3">
                  <div className="font-semibold">{actor.username}</div>
                  <div className="text-sm text-muted-foreground mt-0.5">
                    {actor.account}
                    {actor.email ? ` · ${actor.email}` : ""}
                  </div>
                </div>
                <div className="border-t border-border" />
                <button
                  type="button"
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-4 py-2 text-sm text-destructive hover:bg-muted hover:cursor-pointer"
                >
                  <LogOut className="h-4 w-4" />
                  登出
                </button>
              </div>
            )}
          </div>
        ) : (
          <Button variant="outline" size="sm" onClick={() => router.push("/login")}>
            登入
          </Button>
        )}
      </div>
    </header>
  );
}
