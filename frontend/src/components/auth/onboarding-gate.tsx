'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { getStoredTokens, getStoredUser } from '@/services/auth-service';

/**
 * Defensive onboarding gate, mounted in each dashboard-area layout
 * (dashboard / teacher / org / admin). Primary routing to /onboarding happens at
 * login / code-redeem; this catches a user who navigates or bookmarks straight
 * into a dashboard before finishing onboarding.
 *
 * Only redirects when the cached profile is POSITIVELY incomplete
 * (`is_profile_completed === false`) — a missing/old cached profile (flag
 * undefined) is left alone so we never bounce on stale data or loop.
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
    if (user && user.is_profile_completed === false && !user.is_staff && !user.is_superuser) {
      router.replace('/onboarding');
    }
  }, [pathname, router]);

  return null;
}
