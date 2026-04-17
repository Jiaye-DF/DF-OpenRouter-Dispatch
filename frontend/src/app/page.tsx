import { redirect } from "next/navigation";

// 根路徑：直接導向儀錶板
export default function RootIndex() {
  redirect("/dashboard");
}
