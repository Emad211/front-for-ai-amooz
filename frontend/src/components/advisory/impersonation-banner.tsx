'use client';

import { useEffect, useState } from 'react';
import { LogOut, ShieldQuestion, Timer } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { toPersianDigits } from '@/lib/persian-digits';
import {
  getImpersonationSession,
  IMP_LIFETIME_MS,
  stopImpersonation,
  type ImpersonationSession,
} from '@/services/impersonation-service';

/**
 * The borrowed-session banner — mounted in the advisor and student layouts.
 *
 * A manager wearing someone else's identity must NEVER forget it: the banner
 * is sticky, amber (the one alarm color the panels never use for chrome) and
 * carries the live 30-minute countdown, so the session's expiry is never a
 * surprise. The single exit is `stopImpersonation()` → back to /org/advisory.
 */
export function ImpersonationBanner() {
  const [session, setSession] = useState<ImpersonationSession | null>(null);
  const [remainingMs, setRemainingMs] = useState(0);
  const [stopping, setStopping] = useState(false);

  // Read the session after mount (sessionStorage is client-only; a server
  // render must stay null so the HTML shell never flashes the banner).
  useEffect(() => {
    setSession(getImpersonationSession());
  }, []);

  useEffect(() => {
    if (!session) return;
    const tick = () => setRemainingMs(session.startedAt + IMP_LIFETIME_MS - Date.now());
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [session]);

  if (!session) return null;

  const expired = remainingMs <= 0;
  const clamped = Math.max(remainingMs, 0);
  const minutes = Math.floor(clamped / 60000);
  const seconds = Math.floor((clamped % 60000) / 1000);
  const countdown = `${toPersianDigits(String(minutes).padStart(2, '0'))}:${toPersianDigits(String(seconds).padStart(2, '0'))}`;

  const handleExit = async () => {
    setStopping(true);
    try {
      await stopImpersonation();
    } finally {
      // Full reload so every provider re-reads the restored identity cleanly.
      window.location.href = '/org/advisory';
    }
  };

  return (
    <div
      role="status"
      aria-live="polite"
      className="sticky top-0 z-50 w-full border-b border-amber-700/30 bg-amber-400/95 text-amber-950 backdrop-blur dark:bg-amber-500/90"
      dir="rtl"
    >
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-2 px-3 py-2 sm:px-4">
        <div className="flex min-w-0 items-center gap-2">
          <ShieldQuestion className="h-4 w-4 shrink-0" aria-hidden />
          <p className="truncate text-xs font-bold sm:text-sm">
            ورود مستقیم فعال — شما با حساب «{session.targetName}» مرور می‌کنید
          </p>
          <span
            className={`hidden shrink-0 items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-bold sm:inline-flex ${
              expired
                ? 'bg-red-900/20 text-red-950'
                : 'bg-amber-950/10 text-amber-950/80'
            }`}
          >
            <Timer className="h-3 w-3" aria-hidden />
            {expired ? 'جلسه منقضی شد' : `${countdown} مانده`}
          </span>
        </div>
        <Button
          size="sm"
          variant="outline"
          disabled={stopping}
          onClick={handleExit}
          className="h-7 border-amber-900/40 bg-transparent text-xs font-bold text-amber-950 hover:bg-amber-950/10 hover:text-amber-950"
        >
          <LogOut className="ml-1.5 h-3.5 w-3.5" aria-hidden />
          {stopping ? 'در حال بازگشت…' : 'پایان جلسه و بازگشت'}
        </Button>
      </div>
    </div>
  );
}