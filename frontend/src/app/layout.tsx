import type { Metadata } from "next";
import "./globals.css";
import { ReduxProvider } from "@/store/provider";
import { ThemeManager } from "@/components/layout/ThemeManager";
import { DialogProvider } from "@/lib/dialog";
import { ToasterProvider } from "@/components/ui/toaster";

export const metadata: Metadata = {
  title: "Model Dispatcher",
  description: "Model Dispatcher — OpenRouter API 中控派發管理平台",
};

// Root Layout：載入 ThemeManager、Redux Provider、Toaster、DialogProvider
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-TW" suppressHydrationWarning>
      <body>
        <ReduxProvider>
          <ThemeManager />
          <ToasterProvider>
            <DialogProvider>{children}</DialogProvider>
          </ToasterProvider>
        </ReduxProvider>
      </body>
    </html>
  );
}
