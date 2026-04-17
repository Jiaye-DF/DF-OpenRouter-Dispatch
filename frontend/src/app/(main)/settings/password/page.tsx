"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { PageTitle } from "@/components/common/PageTitle";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { LoadingButton } from "@/components/common/LoadingButton";
import { useDialog } from "@/lib/dialog";
import { apiClient, ApiError } from "@/lib/api/client";
import { API_ENDPOINTS } from "@/lib/api/endpoints";
import { useAppDispatch } from "@/store/hooks";
import { clearAuth } from "@/store/auth-slice";

// 修改自身密碼頁
export default function ChangePasswordPage() {
  const { showDialog } = useDialog();
  const router = useRouter();
  const dispatch = useAppDispatch();
  const [oldPwd, setOldPwd] = React.useState("");
  const [newPwd, setNewPwd] = React.useState("");
  const [confirmPwd, setConfirmPwd] = React.useState("");
  const [saving, setSaving] = React.useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPwd.length < 10) {
      showDialog({
        type: "warning",
        title: "密碼太短",
        message: "新密碼至少 10 字元",
      });
      return;
    }
    if (newPwd !== confirmPwd) {
      showDialog({
        type: "warning",
        title: "密碼不一致",
        message: "兩次輸入的新密碼必須相同",
      });
      return;
    }
    setSaving(true);
    try {
      await apiClient.post(API_ENDPOINTS.changePassword, {
        old_password: oldPwd,
        new_password: newPwd,
      });
      showDialog({
        type: "info",
        title: "已更新",
        message: "密碼已變更，系統將導回登入頁。",
        onConfirm: () => {
          dispatch(clearAuth());
          router.push("/login");
        },
      });
    } catch (err) {
      if (err instanceof ApiError) {
        showDialog({ type: "error", title: "變更失敗", message: err.detail });
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PageTitle
        title="修改密碼"
        description="變更密碼後所有裝置將被登出，需重新登入"
      />
      <Card className="max-w-lg">
        <CardContent className="pt-6">
          <form className="flex flex-col gap-4" onSubmit={onSubmit}>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="old-pwd">舊密碼</Label>
              <Input
                id="old-pwd"
                type="password"
                value={oldPwd}
                onChange={(e) => setOldPwd(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="new-pwd">新密碼（至少 10 字元）</Label>
              <Input
                id="new-pwd"
                type="password"
                value={newPwd}
                onChange={(e) => setNewPwd(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="confirm-pwd">確認新密碼</Label>
              <Input
                id="confirm-pwd"
                type="password"
                value={confirmPwd}
                onChange={(e) => setConfirmPwd(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.push("/dashboard")}
                disabled={saving}
              >
                取消
              </Button>
              <LoadingButton type="submit" loading={saving}>
                更新密碼
              </LoadingButton>
            </div>
          </form>
        </CardContent>
      </Card>
    </>
  );
}
