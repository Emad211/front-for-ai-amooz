'use client';

import { DashboardHeader } from '@/components/layout/dashboard-header';
import { MobileNav } from '@/components/layout/mobile-nav';
import { usePathname, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { getStoredUser } from '@/services/auth-service';
import { DashboardService } from '@/services/dashboard-service';
import { Children, useEffect } from 'react';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const isFocusedMode = pathname.includes('/learn/') || pathname.includes('/exam/');

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const redirectByRole = (role: string) => {
      if (role === 'teacher') {
        router.replace('/teacher');
        return true;
      }
      if (role === 'admin') {
        router.replace('/admin');
        return true;
      }
      return false;
    };

    const storedRole = String(window.localStorage.getItem('userRole') || '').toLowerCase();
    if (storedRole && storedRole !== 'student') {
      redirectByRole(storedRole);
      return;
    }

    // If role isn't cached, try stored user first.
    if (!storedRole) {
      const storedUser = getStoredUser();
      const roleFromUser = String(storedUser?.role || '').toLowerCase();
      if (roleFromUser) {
        window.localStorage.setItem('userRole', roleFromUser);
        if (roleFromUser !== 'student') redirectByRole(roleFromUser);
        return;
      }

      // Final fallback: ask backend.
      DashboardService.getStudentProfile()
        .then((me) => {
          const role = String(me.role || '').toLowerCase();
          if (role) window.localStorage.setItem('userRole', role);
          if (role && role !== 'student') redirectByRole(role);
        })
        .catch(() => {
          // If not authenticated, the underlying service will redirect to login.
        });
    }
  }, [router]);

  return (
    <div className={cn(
      "bg-background text-foreground min-h-screen",
      !isFocusedMode && "pb-20 md:pb-0"
    )}>
      {!isFocusedMode && <DashboardHeader />}
      {Children.toArray(children)}
      {!isFocusedMode && <MobileNav />}
    </div>
  );
}
