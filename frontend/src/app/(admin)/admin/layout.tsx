// app/admin/layout.tsx
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AdminHeader } from "@/components/layout/admin-header";
import { AdminSidebar } from "@/components/layout/admin-sidebar";
import { WorkspaceProvider } from "@/hooks/use-workspace";
import { getStoredUser } from '@/services/auth-service';

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [allowed, setAllowed] = useState<boolean | null>(null);

  useEffect(() => {
    const user = getStoredUser();
    if (!user || (user.role || '').toUpperCase() !== 'ADMIN') {
      router.replace('/login');
    } else {
      setAllowed(true);
    }
  }, [router]);

  // Don't render admin UI until role is verified
  if (!allowed) return null;

  return (
    <WorkspaceProvider>
      <div className="flex min-h-screen w-full bg-background" dir="rtl">
      {/* سایدبار - فقط در دسکتاپ */}
      <div className="hidden lg:block">
        <AdminSidebar />
      </div>
      
      {/* محتوای اصلی */}
      <div className="flex-1 flex flex-col min-w-0">
        <main className="flex-1 p-4 md:p-6 lg:p-8 overflow-x-hidden">
          <AdminHeader />
          <div className="mt-6 md:mt-8">
            {children}
          </div>
        </main>
      </div>
    </div>
    </WorkspaceProvider>
  );
}
