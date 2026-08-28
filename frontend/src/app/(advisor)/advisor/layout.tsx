'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { BookOpen, ClipboardList, Home, LogOut, Users } from 'lucide-react';

import { WorkspaceProvider } from '@/hooks/use-workspace';
import {
  clearAuthStorage,
  getStoredUser,
  logout as logoutApi,
} from '@/services/auth-service';
import { landingFor } from '@/lib/auth-routing';
import { OnboardingGate } from '@/components/auth/onboarding-gate';
import { ImpersonationBanner } from '@/components/advisory/impersonation-banner';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/**
 * Shell for the مشاور (advisor) panel.
 *
 * The nav strip is a flat list rather than a sidebar: the panel will hold a
 * handful of destinations (students, weekly plan, logs), not a tree, and a
 * sidebar holding three links wastes a third of a phone screen in RTL.
 * Destinations are added as their step lands — an entry that leads to a stub
 * reads as a broken panel, not an early one.
 *
 * The header is self-contained rather than reusing TeacherHeader: that component
 * is wired to teaching-specific state (courses, workspace-scoped counters) an
 * advisor has none of.
 */
const NAV = [
  { href: '/advisor', label: 'خانه', icon: Home },
  { href: '/advisor/students', label: 'دانش‌آموزان من', icon: Users },
  { href: '/advisor/subjects', label: 'درس‌ها', icon: BookOpen },
];

export default function AdvisorLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    // Mirrors the teacher guard: a MANAGER goes to /org, a TEACHER to /teacher,
    // a platform ADMIN to /admin, a STUDENT to /home. An unknown/empty role
    // (stale cache before the API resolves) is allowed through — the API's own
    // 401/403 handles auth, and bouncing on stale data causes redirect loops.
    const role = (getStoredUser()?.role || '').toUpperCase();
    if (role && role !== 'ADVISOR') {
      router.replace(landingFor(role));
      return;
    }
    setAllowed(true);
  }, [router]);

  if (!allowed) return null;

  return (
    // WorkspaceProvider is mounted now, before it is used, so the S10 workspace
    // switcher is a component swap rather than a layout rewrite.
    <WorkspaceProvider>
      <OnboardingGate />
      <ImpersonationBanner />
      <div className="flex min-h-screen w-full flex-col bg-background" dir="rtl">
        <header className="border-b border-border/50 bg-card/50 backdrop-blur">
          <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-3 py-3 sm:px-4 md:px-6">
            <Link href="/advisor" className="flex items-center gap-2">
              <span className="rounded-lg bg-primary/10 p-2">
                <ClipboardList className="h-5 w-5 text-primary" />
              </span>
              <span className="text-sm font-bold sm:text-base">پنل مشاور</span>
            </Link>
            <Button
              variant="ghost"
              size="sm"
              onClick={async () => {
                try {
                  // logout() reads the refresh from the HttpOnly cookie,
                  // blacklists it, and clears the cookie server-side.
                  await logoutApi().catch(() => {});
                } finally {
                  clearAuthStorage();
                  window.location.href = '/login';
                }
              }}
              className="text-muted-foreground"
            >
              <LogOut className="ml-2 h-4 w-4" />
              خروج
            </Button>
          </div>
          <nav className="mx-auto flex w-full max-w-6xl gap-1 overflow-x-auto px-3 pb-2 sm:px-4 md:px-6">
            {NAV.map((item) => {
              // Exact match only: '/advisor' is a prefix of every other route, so
              // a startsWith() check would light up the home tab everywhere.
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? 'page' : undefined}
                  className={cn(
                    'flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors sm:text-sm',
                    active
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 overflow-x-hidden p-3 sm:p-4 md:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </WorkspaceProvider>
  );
}
