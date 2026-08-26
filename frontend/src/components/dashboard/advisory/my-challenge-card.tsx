'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Loader2, Lock, Target } from 'lucide-react';

import {
  AdvisoryService,
  type Challenge,
  type ChallengeDay,
} from '@/services/advisory-service';
import { formatPersianDate } from '@/lib/date-utils';
import { toPersianDigits } from '@/lib/persian-digits';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import {
  CHALLENGE_STATUS_BADGE_CLASSES,
  CHALLENGE_STATUS_LABELS,
} from '@/components/advisory/challenge-card';

const DAYS_PER_CHALLENGE = 7;

function parseIsoDate(iso: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(date.getTime()) ? null : date;
}

function toIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatJalaliDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return formatPersianDate(parseIsoDate(iso) ?? iso);
}

/** Absolute ISO date of day N (`startDate + N - 1`), or null on bad input. */
function challengeDayIso(startDate: string, dayNumber: number): string | null {
  const base = parseIsoDate(startDate);
  if (!base) return null;
  return toIsoDate(
    new Date(base.getFullYear(), base.getMonth(), base.getDate() + dayNumber - 1),
  );
}

function seedDays(challenge: Challenge): ChallengeDay[] {
  return Array.from({ length: DAYS_PER_CHALLENGE }, (_, i) => {
    const found = (challenge.days ?? []).find((d) => d.dayNumber === i + 1);
    return {
      dayNumber: i + 1,
      goal: found?.goal ?? '',
      summary: found?.summary ?? '',
    };
  });
}

/**
 * The student-side challenge card («چالش هفت‌روزه», restart step 9): shows the
 * ACTIVE challenge (or the latest one) with a 7-day editor where ONLY
 * goal+summary are writable and ONLY for days whose date has arrived — future
 * days render disabled with a hint. The server re-enforces both rules; its
 * Persian details (including the no-advisor 409) surface verbatim via toast.
 *
 * Quiet home-card rule: renders NOTHING without an active advisor AND a
 * challenge to show; failed fetches are swallowed by design.
 */
export function MyChallengeCard() {
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [rows, setRows] = useState<ChallengeDay[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    AdvisoryService.getMyChallenges()
      .then((resp) => {
        if (!active || !resp.active) return;
        const list = Array.isArray(resp.challenges) ? resp.challenges : [];
        // ACTIVE wins; otherwise the most recently created one.
        const sorted = [...list].sort((a, b) => b.id - a.id);
        const picked =
          sorted.find((c) => c.status === 'ACTIVE') ?? sorted[0] ?? null;
        if (picked) setChallenge(picked);
      })
      .catch(() => {
        // Silent by design — see the component docstring.
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (challenge) setRows(seedDays(challenge));
  }, [challenge]);

  if (!challenge) return null;

  // Computed once per mount — a stale boundary at midnight is harmless.
  const todayIso = toIsoDate(new Date());

  const updateRow = (
    dayNumber: number,
    patch: Partial<Omit<ChallengeDay, 'dayNumber'>>,
  ) => {
    setRows((prev) =>
      prev.map((row) =>
        row.dayNumber === dayNumber ? { ...row, ...patch } : row,
      ),
    );
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await AdvisoryService.putMyChallengeDays(
        challenge.id,
        rows.map(({ dayNumber, goal, summary }) => ({
          dayNumber,
          goal,
          summary,
        })),
      );
      toast.success('روزهای چالش ذخیره شد.');
    } catch (err: unknown) {
      // Includes «فقط هدف و خلاصهٔ روز…» / future-day 400s verbatim.
      toast.error(
        err instanceof Error ? err.message : 'ذخیرۀ روزهای چالش ناموفق بود.',
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card dir="rtl" className="rounded-2xl border-primary/20 bg-primary/5">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-base font-semibold">
            <span className="rounded-lg bg-primary/10 p-1.5">
              <Target className="h-4 w-4 text-primary" />
            </span>
            چالش هفت‌روزه
          </CardTitle>
          <span
            className={cn(
              'shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold',
              CHALLENGE_STATUS_BADGE_CLASSES[challenge.status],
            )}
          >
            {CHALLENGE_STATUS_LABELS[challenge.status]}
          </span>
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          هر روزِ رسیده را پر کنید؛ هدف و خلاصۀ روزهای آینده تا فرا رسیدنشان
          بسته است.
        </p>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="space-y-1 rounded-xl border border-border/60 bg-background/60 p-3">
          <p className="text-sm font-medium leading-relaxed">
            {challenge.title || 'بدون عنوان'}
          </p>
          <p className="text-xs tabular-nums text-muted-foreground">
            {formatJalaliDate(challenge.startDate)} تا{' '}
            {formatJalaliDate(challenge.endDate)}
          </p>
          {challenge.goalText.trim() && (
            <p className="whitespace-pre-line pt-1 text-xs leading-relaxed">
              {challenge.goalText}
            </p>
          )}
          {challenge.dailyRoutine.trim() && (
            <p className="pt-1 text-xs text-muted-foreground">
              روتین روزانه: {challenge.dailyRoutine}
            </p>
          )}
        </div>

        <ul className="space-y-2">
          {rows.map((row) => {
            const dayIso = challengeDayIso(challenge.startDate, row.dayNumber);
            const editable = dayIso !== null && dayIso <= todayIso;
            return (
              <li
                key={row.dayNumber}
                className={cn(
                  'space-y-1.5 rounded-lg border p-2',
                  editable ? 'border-border/50' : 'border-border/30 opacity-70',
                )}
              >
                <p className="flex flex-wrap items-center gap-x-2 text-xs font-medium">
                  <span>روز {toPersianDigits(row.dayNumber)}</span>
                  {dayIso && (
                    <span className="tabular-nums text-muted-foreground">
                      ({formatJalaliDate(dayIso)})
                    </span>
                  )}
                  {!editable && (
                    <span className="inline-flex items-center gap-1 text-muted-foreground">
                      <Lock className="h-3 w-3" />
                      هنوز فرا نرسیده است
                    </span>
                  )}
                </p>
                <Input
                  value={row.goal}
                  onChange={(e) =>
                    updateRow(row.dayNumber, { goal: e.target.value })
                  }
                  disabled={!editable || saving}
                  placeholder={`هدف‌گذاری روز ${toPersianDigits(row.dayNumber)}`}
                  maxLength={200}
                  aria-label={`هدف روز ${toPersianDigits(row.dayNumber)}`}
                  aria-disabled={!editable}
                  className="h-9 text-xs"
                />
                <Textarea
                  value={row.summary}
                  onChange={(e) =>
                    updateRow(row.dayNumber, { summary: e.target.value })
                  }
                  disabled={!editable || saving}
                  rows={3}
                  maxLength={5000}
                  placeholder="خلاصۀ کارها، مشکلات و نتیجهٔ امروز…"
                  aria-label={`خلاصۀ روز ${toPersianDigits(row.dayNumber)}`}
                  aria-disabled={!editable}
                  className="min-h-[72px] text-xs leading-relaxed"
                />
              </li>
            );
          })}
        </ul>

        <div className="flex items-center justify-end border-t border-border/60 pt-3">
          <Button type="button" onClick={handleSave} disabled={saving}>
            {saving && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
            {saving ? 'در حال ذخیره…' : 'ذخیرۀ روزها'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
