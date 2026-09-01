'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { fetchMe, getStoredTokens, getStoredUser, persistUser } from '@/services/auth-service';

/**
 * Defensive onboarding gate for the dashboard-area layouts (dashboard / teacher
 * / org / admin). Primary routing to /onboarding happens at login / code-redeem.
 *
 * Invariant: the cached profile is only a HINT. When it is positively
 * incomplete we re-check /me BEFORE bouncing, so a stale cache can never trap
 * a user in an onboarding loop. Redirect only on a fresh positive ``false``.
 */
export function OnboardingGate() {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (pathname?.startsWith('/onboarding')) return;
    const tokens = getStoredTokens();
    if (!tokens?.access) return;
    const user = getStoredUser();
    // Platform admins/superusers are never code-onboarded — exempt them even if
    // the flag is false (e.g. a createsuperuser account).
    if (!user || user.is_profile_completed !== false || user.is_staff || user.is_superuser) return;

    let cancelled = false;
    void (async () => {
      try {
        const fresh = await fetchMe();
        if (cancelled) return;
        persistUser(fresh);
        if (fresh.is_profile_completed === false && !fresh.is_staff && !fresh.is_superuser) {
          router.replace('/onboarding');
        }
      } catch {
        // /me unreachable (offline/expired token): never bounce on stale data —
        // the auth layer owns token invalidation.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  return null;
}
