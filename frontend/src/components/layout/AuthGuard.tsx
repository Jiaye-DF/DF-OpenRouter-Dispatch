"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { clearAuth, setActor, setAuthLoading } from "@/store/auth-slice";
import { Spinner } from "@/components/ui/spinner";
import type { Actor } from "@/types/api";

// AuthGuard：(main) 群組首次掛載時取 /auth/me；失敗則導 /login。
// 用 ref 鎖首次執行，避免 setAuthLoading 改 state 後 effect 重跑、
// cleanup 把 cancelled=true，導致 catch 提早 return、永遠停在 loading。
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const dispatch = useAppDispatch();
  const router = useRouter();
  const status = useAppSelector((s) => s.auth.status);
  const startedRef = React.useRef(false);

  // 取 actor 只跑一次（ref 防 StrictMode 雙呼叫）
  React.useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    (async () => {
      dispatch(setAuthLoading());
      try {
        const actor = await apiClient.get<Actor>(API_ENDPOINTS.me);
        dispatch(setActor(actor));
      } catch (err) {
        dispatch(clearAuth());
        // ApiError 只用於記錄；redirect 交給下方 effect 依 status 反應
        void (err as ApiError);
      }
    })();
  }, [dispatch]);

  // status 轉 unauthenticated 時一律導 /login
  React.useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  if (status === "idle" || status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size={24} />
      </div>
    );
  }
  if (status === "unauthenticated") return null;
  return <>{children}</>;
}
