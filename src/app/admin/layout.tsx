import { AdminHeader } from "@/components/layout/admin-header";
import { AdminSidebar } from "@/components/layout/admin-sidebar";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen w-full bg-background" dir="rtl">
        <div className="flex flex-1 flex-row-reverse">
            <AdminSidebar />
            <main className="flex-1 p-4 md:p-8">
                <AdminHeader />
                {children}
            </main>
        </div>
    </div>
  );
}
