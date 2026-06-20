'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  fetchMe,
  getStoredTokens,
  getStoredUser,
  persistUser,
} from '@/services/auth-service';
import { landingFor } from '@/lib/auth-routing';

/**
 * Guard for the forced onboarding flow. Lives at TOP level (outside every
 * dashboard/auth route group) so the role guards can't bounce it and
 * AuthAutoRedirect never sees it.
 *
 * - No session → /login.
 * - Already completed → their dashboard (landingFor).
 * - Otherwise render the wizard. A best-effort fetchMe() reconciles a stale or
 *   missing cached user (org-redeem persists the user via a swallowed fetchMe).
 */
export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const tokens = getStoredTokens();
    if (!tokens?.access) {
      router.replace('/login');
      return;
    }

    // Already done with onboarding, or a platform admin who never needs it.
    const noOnboardingNeeded = (u: { is_profile_completed?: boolean; is_staff?: boolean; is_superuser?: boolean } | null) =>
      !!u && (u.is_profile_completed || u.is_staff || u.is_superuser);

    const cached = getStoredUser();
    if (noOnboardingNeeded(cached)) {
      router.replace(landingFor(cached!.role));
      return;
    }

    let cancelled = false;
    fetchMe()
      .then((me) => {
        if (cancelled) return;
        persistUser(me);
        if (noOnboardingNeeded(me)) router.replace(landingFor(me.role));
        else setReady(true);
      })
      .catch(() => {
        // Backend unreachable — still let them try to onboard from cached state.
        if (!cancelled) setReady(true);
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  if (!ready) return null;

  return (
    <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-4">
      {children}
    </div>
  );
}
