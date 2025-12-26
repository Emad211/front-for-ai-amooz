import { AdminHeader } from "@/components/layout/admin-header";
import { AdminSidebar } from "@/components/layout/admin-sidebar";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen w-full flex-col bg-background" dir="rtl">
        <div className="flex flex-1">
            <main className="flex-1 p-4 md:p-8">
                <AdminHeader />
                {children}
            </main>
            <AdminSidebar />
        </div>
    </div>
  );
}
