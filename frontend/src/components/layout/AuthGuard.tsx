"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { clearAuth, setActor, setAuthLoading } from "@/store/auth-slice";
import { Spinner } from "@/components/ui/spinner";
import type { Actor } from "@/types/api";

// AuthGuard：(main) 群組首次掛載時取 /auth/me；失敗則導 /login
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const dispatch = useAppDispatch();
  const router = useRouter();
  const status = useAppSelector((s) => s.auth.status);

  React.useEffect(() => {
    let cancelled = false;
    async function run() {
      dispatch(setAuthLoading());
      try {
        const actor = await apiClient.get<Actor>(API_ENDPOINTS.me);
        if (cancelled) return;
        dispatch(setActor(actor));
      } catch (err) {
        if (cancelled) return;
        dispatch(clearAuth());
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
        }
      }
    }
    if (status === "idle") {
      run();
    }
    return () => {
      cancelled = true;
    };
  }, [dispatch, router, status]);

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
