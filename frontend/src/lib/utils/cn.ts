import clsx, { type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// 合併 class 名稱並去除衝突：clsx + tailwind-merge 標準組合
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
