"use client";

import * as React from "react";
import { Button, type ButtonProps } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

interface LoadingButtonProps extends ButtonProps {
  loading?: boolean;
}

// 封裝 Button + 自動 disabled + spinner，確保 pending 期間無法重複點擊
export const LoadingButton = React.forwardRef<
  HTMLButtonElement,
  LoadingButtonProps
>(({ loading, disabled, children, ...props }, ref) => {
  return (
    <Button ref={ref} disabled={disabled || loading} {...props}>
      {loading && <Spinner size={14} />}
      {children}
    </Button>
  );
});
LoadingButton.displayName = "LoadingButton";
