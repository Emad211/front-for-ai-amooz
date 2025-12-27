'use client';

import { DashboardHeader } from '@/components/layout/dashboard-header';
import { MobileNav } from '@/components/layout/mobile-nav';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const isFocusedMode = pathname.includes('/learn/') || pathname.includes('/exam/');

  return (
    <div className={cn(
      "bg-background text-foreground min-h-screen",
      !isFocusedMode && "pb-20 md:pb-0"
    )}>
      {!isFocusedMode && <DashboardHeader />}
      {children}
      {!isFocusedMode && <MobileNav />}
    </div>
  );
}
