'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { HeartHandshake, LogOut } from 'lucide-react';

import {
  clearAuthStorage,
  getStoredUser,
  logout as logoutApi,
} from '@/services/auth-service';
import { landingFor } from '@/lib/auth-routing';
import { Button } from '@/components/ui/button';

/**
 * Shell for the والد (parent) read-only digest panel.
 *
 * Mirrors the advisor role guard: any known non-PARENT role is bounced to its
 * own landing route via landingFor(); an unknown/empty role (stale cache
 * before the API resolves) is allowed through — the API's own 401/403 handles
 * auth, and bouncing on stale data causes redirect loops.
 *
 * Deliberately no WorkspaceProvider / OnboardingGate / ImpersonationBanner:
 * a parent has no workspace, arrives with is_profile_completed=true per the
 * contract, and is never an impersonation target. The panel is a single
 * read-only page, so there is no navigation strip — only a header and خروج.
 */
export default function ParentLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    const role = (getStoredUser()?.role || '').toUpperCase();
    if (role && role !== 'PARENT') {
      router.replace(landingFor(role));
      return;
    }
    setAllowed(true);
  }, [router]);

  if (!allowed) return null;

  return (
    <div className="flex min-h-screen w-full flex-col bg-background" dir="rtl">
      <header className="border-b border-border/50 bg-card/50 backdrop-blur">
        <div className="mx-auto flex w-full max-w-4xl items-center justify-between gap-3 px-3 py-3 sm:px-4 md:px-6">
          <Link href="/parent" className="flex items-center gap-2">
            <span className="rounded-lg bg-primary/10 p-2">
              <HeartHandshake className="h-5 w-5 text-primary" />
            </span>
            <span className="text-sm font-bold sm:text-base">
              گزارش فرزند من
            </span>
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
                window.location.href = '/parent-login';
              }
            }}
            className="h-11 rounded-xl px-3 text-muted-foreground"
          >
            <LogOut className="ml-2 h-4 w-4" />
            خروج
          </Button>
        </div>
      </header>
      <main className="mx-auto w-full max-w-4xl flex-1 overflow-x-hidden p-3 sm:p-4 md:p-6 lg:p-8">
        {children}
      </main>
    </div>
  );
}
