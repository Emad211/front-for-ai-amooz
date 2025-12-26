// app/admin/layout.tsx
import { AdminHeader } from "@/components/layout/admin-header";
import { AdminSidebar } from "@/components/layout/admin-sidebar";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen w-full bg-background" dir="rtl">
      {/* سایدبار - سمت راست */}
      <AdminSidebar />
      
      {/* محتوای اصلی */}
      <div className="flex-1 flex flex-col">
        <main className="flex-1 p-6 md:p-8 overflow-auto">
          <AdminHeader />
          <div className="mt-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
