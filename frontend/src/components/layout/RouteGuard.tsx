"use client";

import * as React from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAppSelector } from "@/store/hooks";

// 非 admin 僅允許這些路徑；其餘 (main) 路由一律視為 admin 專用，新增頁面自動受保護。
const MEMBER_ALLOWED_PREFIXES = [
  "/dashboard",
  "/user-guide",
  "/api-key-requests",
  "/usage-logs",
];

function isMemberAllowed(pathname: string): boolean {
  return MEMBER_ALLOWED_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );
}

// RouteGuard：集中式角色守衛，置於 AuthGuard 內（actor 必已載入）。
// 非 admin 進入 admin 專用路由時導回 /dashboard；真正權限仍由後端 AdminDep 把關。
export function RouteGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const role = useAppSelector((s) => s.auth.actor?.role);

  const blocked = role !== "admin" && !isMemberAllowed(pathname);

  React.useEffect(() => {
    if (blocked) router.replace("/dashboard");
  }, [blocked, router]);

  // 導向前先不渲染內容，避免 admin 頁面瞬間閃現
  if (blocked) return null;
  return <>{children}</>;
}
