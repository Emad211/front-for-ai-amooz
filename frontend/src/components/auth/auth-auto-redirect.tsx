'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { getStoredTokens, getStoredUser } from '@/services/auth-service';

/**
 * Bounce an already-authenticated user away from login/signup pages to their
 * dashboard. Mounted once in the (auth) layout.
 *
 * Exceptions: the code-join pages, where a signed-in user can legitimately
 * redeem a code (e.g. a teacher joining another org), and the registration-
 * completion link (creates a fresh account from a waitlist token).
 */
const ALLOW_WHEN_AUTHED = ['/join-code', '/join', '/org-login', '/register'];

function dashboardFor(role: string | undefined): string {
  const r = (role || '').toLowerCase();
  if (r === 'admin') return '/admin';
  if (r === 'teacher' || r === 'manager') return '/teacher';
  return '/home';
}

export function AuthAutoRedirect() {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (ALLOW_WHEN_AUTHED.some((p) => pathname?.startsWith(p))) return;
    const tokens = getStoredTokens();
    if (!tokens?.access) return;
    // The dashboard layouts re-assert role routing, so a stale cached role
    // self-corrects; default to the student home.
    router.replace(dashboardFor(getStoredUser()?.role));
  }, [pathname, router]);

  return null;
}
