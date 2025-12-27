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
      {/* سایدبار - فقط در دسکتاپ */}
      <div className="hidden lg:block">
        <AdminSidebar />
      </div>
      
      {/* محتوای اصلی */}
      <div className="flex-1 flex flex-col min-w-0">
        <main className="flex-1 p-4 md:p-8 overflow-auto">
          <AdminHeader />
          <div className="mt-6 md:mt-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
