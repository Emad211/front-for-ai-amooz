'use client';

import Link from 'next/link';
import {
  ChevronLeft,
  Clock,
  Flame,
  Target,
  TrendingUp,
  UserPlus,
  Users,
  type LucideIcon,
} from 'lucide-react';

import type { AdvisorStudent } from '@/services/advisory-service';
import { formatPersianPercent, toPersianDigits } from '@/lib/persian-digits';
import { Card } from '@/components/ui/card';

/** A roster student joined with its (optional) overview enrichment row. */
export type MergedAdvisorStudent = {
  student: AdvisorStudent;
  adherence7d: number | null;
  lastLogDate: string | null;
  activeChallengeTitle: string | null;
};

/* ── status dot ────────────────────────────────────────────────────────── */

const STATUS_DOTS: Record<string, { label: string; dotClass: string }> = {
  ACTIVE: { label: 'فعال', dotClass: 'bg-emerald-500' },
  PENDING: { label: 'در انتظار', dotClass: 'bg-amber-500' },
  ENDED: { label: 'پایان‌یافته', dotClass: 'bg-muted-foreground/40' },
  REJECTED: { label: 'رد شده', dotClass: 'bg-muted-foreground/40' },
};

function StatusDot({ status }: { status: AdvisorStudent['status'] }) {
  const meta = STATUS_DOTS[status] ?? STATUS_DOTS.ENDED;
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5">
      <span aria-hidden className={`h-2 w-2 rounded-full ${meta.dotClass}`} />
      <span className="text-xs text-muted-foreground">{meta.label}</span>
    </span>
  );
}

/* ── adherence colors ──────────────────────────────────────────────────── */

function adherenceBarClass(percent: number): string {
  if (percent >= 80) return 'bg-emerald-500';
  if (percent >= 50) return 'bg-amber-500';
  return 'bg-red-500';
}

/** Plain text-color twin of `adherenceBarClass` — no pill, no background. */
function adherenceTextClass(percent: number): string {
  if (percent >= 80) return 'text-emerald-500';
  if (percent >= 50) return 'text-amber-500';
  return 'text-red-500';
}

/**
 * «۳ روز پیش» from an ISO `YYYY-MM-DD` log date — «امروز»/«دیروز» collapse
 * the near cases; `null`/unparseable renders «هرگز».
 */
export function relativeLastLogLabel(lastLogDate: string | null): string {
  if (!lastLogDate) return 'هرگز';
  const then = new Date(`${lastLogDate}T00:00:00`);
  if (Number.isNaN(then.getTime())) return 'هرگز';
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const diffDays = Math.round((startOfToday.getTime() - then.getTime()) / 86_400_000);
  if (diffDays <= 0) return 'امروز';
  if (diffDays === 1) return 'دیروز';
  return `${toPersianDigits(diffDays)} روز پیش`;
}

/* ── stat strip ────────────────────────────────────────────────────────── */

type StatCellProps = {
  icon: LucideIcon;
  label: string;
  value: React.ReactNode;
  valueClassName?: string;
};

function StatCell({ icon: Icon, label, value, valueClassName }: StatCellProps) {
  return (
    <div className="flex min-w-0 items-center gap-2.5 border-s border-border/40 px-3 py-0.5 first:border-s-0 first:ps-0 last:pe-0 sm:px-4">
      <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0">
        <p
          className={`text-2xl font-bold leading-none tabular-nums ${valueClassName ?? ''}`}
        >
          {value}
        </p>
        <p className="mt-1 truncate text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

export type AdvisorStatStripProps = {
  activeStudents: number;
  pendingInvites: number;
  averageAdherence7d: number | null;
  activeChallengeCount: number;
};

/**
 * The four headline counters of the advisor cockpit as ONE soft card row:
 * adherence renders as plain threshold-colored text; a pending count >0
 * tints its value amber.
 */
export function AdvisorStatStrip({
  activeStudents,
  pendingInvites,
  averageAdherence7d,
  activeChallengeCount,
}: AdvisorStatStripProps) {
  const hasPending = pendingInvites > 0;
  return (
    <Card className="rounded-2xl border-border/50">
        <div className="grid grid-cols-4 p-5">
        <StatCell
          icon={Users}
          label="دانش‌آموزان فعال"
          value={toPersianDigits(activeStudents)}
        />
        <StatCell
          icon={UserPlus}
          label="در انتظار تأیید"
          value={toPersianDigits(pendingInvites)}
          valueClassName={hasPending ? 'text-amber-500' : undefined}
        />
        <StatCell
          icon={TrendingUp}
          label="میانگین تعهد ۷روزه"
          value={
            averageAdherence7d === null ? (
              '—'
            ) : (
              <span className={adherenceTextClass(averageAdherence7d)}>
                {formatPersianPercent(averageAdherence7d)}
              </span>
            )
          }
        />
        <StatCell
          icon={Flame}
          label="چالش فعال"
          value={toPersianDigits(activeChallengeCount)}
        />
      </div>
    </Card>
  );
}

/* ── student card ──────────────────────────────────────────────────────── */

/** One roster card of the cockpit grid; the whole card links to the student. */
export function AdvisorStudentCardView({
  entry,
}: {
  entry: MergedAdvisorStudent;
}) {
  const { student, adherence7d, lastLogDate, activeChallengeTitle } = entry;

  return (
    <Link
      href={`/advisor/students/${student.id}`}
      className="group block h-full rounded-2xl focus-visible:outline-none"
    >
      <Card className="flex h-full flex-col rounded-2xl border-border/50 transition-colors hover:border-primary/40 hover:bg-muted/30 focus-visible:border-primary focus-visible:ring-1 focus-visible:ring-ring">
        <div className="flex h-full flex-col gap-3 p-5">
          <div className="flex items-center justify-between gap-2">
            <p className="min-w-0 truncate text-base font-semibold">
              {student.studentName}
            </p>
            <span className="flex shrink-0 items-center gap-2">
              <StatusDot status={student.status} />
              <ChevronLeft
                aria-hidden
                className="h-4 w-4 text-muted-foreground opacity-40 transition-all group-hover:-translate-x-0.5 group-hover:opacity-100"
              />
            </span>
          </div>

          {adherence7d === null ? (
            <p className="text-xs leading-relaxed text-muted-foreground">
              برنامه‌ای این هفته نیست
            </p>
          ) : (
            <div className="flex items-center gap-2.5">
              <div
                role="progressbar"
                aria-valuenow={adherence7d}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`تعهد هفتگی ${student.studentName}`}
                className="h-1 flex-1 overflow-hidden rounded-full bg-muted"
              >
                <div
                  className={`h-full rounded-full transition-all ${adherenceBarClass(adherence7d)}`}
                  style={{ width: `${Math.min(100, Math.max(0, adherence7d))}%` }}
                />
              </div>
              <span
                className={`shrink-0 text-xs font-medium tabular-nums ${adherenceTextClass(adherence7d)}`}
              >
                {formatPersianPercent(adherence7d)}
              </span>
            </div>
          )}

          <div className="mt-auto space-y-1">
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Clock className="h-3.5 w-3.5 shrink-0" />
              آخرین گزارش: {relativeLastLogLabel(lastLogDate)}
            </p>
            {activeChallengeTitle && (
              <p className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
                <Target className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate" title={activeChallengeTitle}>
                  {activeChallengeTitle}
                </span>
              </p>
            )}
          </div>
        </div>
      </Card>
    </Link>
  );
}
