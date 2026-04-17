"use client";

import { Button } from "@/components/ui/button";

// 頁面級錯誤邊界
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="min-h-[50vh] flex flex-col items-center justify-center gap-4 p-8 text-center">
      <h2 className="text-xl font-semibold">發生了預期外的錯誤</h2>
      <p className="text-sm text-muted-foreground max-w-md break-all">
        {error.message || "請稍後再試。"}
      </p>
      <Button onClick={() => reset()}>重新載入</Button>
    </div>
  );
}
