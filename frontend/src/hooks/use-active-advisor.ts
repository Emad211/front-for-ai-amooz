'use client';

/**
 * Shared "does this student currently have an ACTIVE advisor?" signal.
 *
 * The promise lives at module level so every consumer mounted in the same pass
 * (desktop pill nav + mobile bottom bar) shares ONE network call instead of
 * duplicating it. It is dropped once settled, so later mounts re-check fresh —
 * a student who accepts an invite sees the nav entry on their next navigation
 * without a reload.
 *
 * `null` means "still loading": callers must render NOTHING in that state, so
 * the entry never flashes for students without an advisor. Failures resolve to
 * `false` on purpose (banner semantics — advisory UI stays quiet when the
 * engagement read fails).
 */

import { useEffect, useState } from 'react';

import { AdvisoryService } from '@/services/advisory-service';

let inFlight: Promise<boolean> | null = null;

function requestHasActiveAdvisor(): Promise<boolean> {
  if (!inFlight) {
    inFlight = AdvisoryService.getMyEngagement()
      .then((data) => data.active !== null)
      .catch(() => false)
      .finally(() => {
        // Concurrent callers already hold this exact promise instance; later
        // mounts should get a fresh check instead of a stale cached answer.
        inFlight = null;
      });
  }
  return inFlight;
}

export function useActiveAdvisor(): { hasActiveAdvisor: boolean | null } {
  const [hasActiveAdvisor, setHasActiveAdvisor] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;
    void requestHasActiveAdvisor().then((value) => {
      if (active) setHasActiveAdvisor(value);
    });
    return () => {
      active = false;
    };
  }, []);

  return { hasActiveAdvisor };
}
