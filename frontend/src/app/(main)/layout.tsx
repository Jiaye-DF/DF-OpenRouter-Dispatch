import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { AuthGuard } from "@/components/layout/AuthGuard";
import { RouteGuard } from "@/components/layout/RouteGuard";

// 已登入主群組：Header + Sidebar + 置中主內容；各頁面只負責填 PageTitle + Card
export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <div className="min-h-screen flex flex-col">
        <Header />
        <div className="flex flex-1">
          <Sidebar />
          <main className="flex-1 min-w-0">
            <div className="mx-4 my-6 md:mx-12 md:my-8 max-w-screen-2xl">
              <RouteGuard>{children}</RouteGuard>
            </div>
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}
