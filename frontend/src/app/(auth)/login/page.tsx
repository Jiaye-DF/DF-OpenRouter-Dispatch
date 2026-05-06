"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
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

export default function LoginPage() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const { showDialog } = useDialog();
  const [submitting, setSubmitting] = React.useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    mode: "onSubmit",
  });

  const onSubmit = async (values: LoginForm) => {
    // 手動檢核（不引入 @hookform/resolvers 以精簡依賴）
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
      if (err instanceof ApiError) {
        showDialog({
          type: "error",
          title: "無法登入",
          message: "帳號或密碼錯誤",
        });
      } else {
        showDialog({
          type: "error",
          title: "無法登入",
          message: "請稍後再試",
        });
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="items-center text-center">
        <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
          <Zap className="h-6 w-6" />
        </div>
        <CardTitle>Model Dispatcher</CardTitle>
        <CardDescription>登入以管理部門 Key 與用量</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit(onSubmit)}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="account">帳號</Label>
            <Input
              id="account"
              autoComplete="username"
              {...register("account")}
              disabled={submitting}
            />
            {errors.account && (
              <p className="text-sm text-destructive">{errors.account.message}</p>
            )}
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
            {errors.password && (
              <p className="text-sm text-destructive">{errors.password.message}</p>
            )}
          </div>
          <LoadingButton type="submit" loading={submitting} className="mt-2">
            登入
          </LoadingButton>
        </form>
      </CardContent>
    </Card>
  );
}
