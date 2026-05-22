"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Zap } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { LoadingButton } from "@/components/common/LoadingButton";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { useAppDispatch } from "@/store/hooks";
import { setActor } from "@/store/auth-slice";
import { useDialog } from "@/lib/dialog";
import type { Actor } from "@/types/api";

// 登入 schema：account 最少 4 字，password 最少 10 字
const loginSchema = z.object({
  account: z.string().min(4, "帳號至少 4 個字元"),
  password: z.string().min(10, "密碼至少 10 個字元"),
});

type LoginForm = z.infer<typeof loginSchema>;

// SSO callback 失敗時 ?error= 帶回的代碼對照（與後端 services/sso.py 的 SsoError reason 一致）
const SSO_ERROR_MESSAGES: Record<string, string> = {
  sso_no_account: "此帳號尚未開通管理後台權限,請聯絡系統管理員。",
  sso_not_admin: "此帳號無管理後台存取權限。",
  sso_inactive: "此帳號已停用,請聯絡系統管理員。",
  sso_no_email: "DF-SSO 未提供 Email,無法對應系統帳號。",
  no_code: "登入流程中斷,請重新登入。",
  exchange_failed: "登入驗證失敗,請重新登入。",
  exchange_error: "無法連線 DF-SSO,請稍後再試。",
  session_expired: "登入狀態已逾期,請重新登入。",
  sso_unreachable: "無法連線 DF-SSO,請稍後再試。",
  sso_not_configured: "尚未設定 DF-SSO,請改用帳號密碼登入或聯絡管理員。",
};

function LoginInner() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const searchParams = useSearchParams();
  const { showDialog } = useDialog();

  // 進頁先打 /me：已登入直接進 dashboard,未登入才顯示登入畫面
  const [checking, setChecking] = React.useState(true);
  const [submitting, setSubmitting] = React.useState(false);
  const startedRef = React.useRef(false);

  const errorCode = searchParams.get("error");
  const loggedOut = searchParams.get("logged_out") === "1";

  const { register, handleSubmit } = useForm<LoginForm>({ mode: "onSubmit" });

  React.useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    (async () => {
      try {
        const actor = await apiClient.get<Actor>(API_ENDPOINTS.me);
        dispatch(setActor(actor));
        router.replace("/dashboard");
      } catch {
        setChecking(false);
      }
    })();
  }, [dispatch, router]);

  // 帳號密碼登入（與 DF-SSO 並存,供本機開發與 SSO 不可用時使用）
  const onSubmit = async (values: LoginForm) => {
    const parsed = loginSchema.safeParse(values);
    if (!parsed.success) {
      const first = parsed.error.issues[0];
      showDialog({ type: "error", title: "欄位錯誤", message: first.message });
      return;
    }
    setSubmitting(true);
    try {
      await apiClient.post(API_ENDPOINTS.login, parsed.data);
      const actor = await apiClient.get<Actor>(API_ENDPOINTS.me);
      dispatch(setActor(actor));
      router.push("/dashboard");
    } catch (err) {
      // 登入失敗統一顯示「帳號或密碼錯誤」，避免帳號列舉
      showDialog({
        type: "error",
        title: "無法登入",
        message: err instanceof ApiError ? "帳號或密碼錯誤" : "請稍後再試",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleSsoLogin = () => {
    const base = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");
    window.location.href = `${base}${API_ENDPOINTS.ssoLogin}`;
  };

  const errorMessage = errorCode
    ? (SSO_ERROR_MESSAGES[errorCode] ?? "登入失敗,請重新登入。")
    : null;

  if (checking) {
    return (
      <div className="flex min-h-[180px] items-center justify-center">
        <Spinner size={24} />
      </div>
    );
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="items-center text-center">
        <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
          <Zap className="h-6 w-6" />
        </div>
        <CardTitle>Model Dispatcher</CardTitle>
        <CardDescription>登入以管理部門 Key 與用量</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {loggedOut && !errorMessage && (
          <p className="rounded-md bg-muted px-3 py-2 text-center text-sm text-muted-foreground">
            您已成功登出。
          </p>
        )}
        {errorMessage && (
          <p className="rounded-md bg-destructive/10 px-3 py-2 text-center text-sm text-destructive">
            {errorMessage}
          </p>
        )}

        <Button onClick={handleSsoLogin} className="w-full">
          透過 DF-SSO 登入
        </Button>

        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="h-px flex-1 bg-border" />
          或使用帳號密碼
          <span className="h-px flex-1 bg-border" />
        </div>

        <form className="flex flex-col gap-4" onSubmit={handleSubmit(onSubmit)}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="account">帳號</Label>
            <Input
              id="account"
              autoComplete="username"
              {...register("account")}
              disabled={submitting}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password">密碼</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              {...register("password")}
              disabled={submitting}
            />
          </div>
          <LoadingButton type="submit" loading={submitting} variant="outline">
            帳號密碼登入
          </LoadingButton>
        </form>
      </CardContent>
    </Card>
  );
}

export default function LoginPage() {
  // useSearchParams 需置於 Suspense 邊界內（Next.js App Router build 要求）
  return (
    <React.Suspense
      fallback={
        <div className="flex min-h-[180px] items-center justify-center">
          <Spinner size={24} />
        </div>
      }
    >
      <LoginInner />
    </React.Suspense>
  );
}
