'use client';

import Link from 'next/link';
import {
  ArrowLeft,
  Clock,
  Flame,
  Target,
  TrendingUp,
  UserPlus,
  Users,
  type LucideIcon,
} from 'lucide-react';

import type { AdvisorStudent } from '@/services/advisory-service';
import { adherenceColorClass } from '@/lib/adherence';
import { formatPersianPercent, toPersianDigits } from '@/lib/persian-digits';
import { Card, CardContent } from '@/components/ui/card';

/** A roster student joined with its (optional) overview enrichment row. */
export type MergedAdvisorStudent = {
  student: AdvisorStudent;
  adherence7d: number | null;
  lastLogDate: string | null;
  activeChallengeTitle: string | null;
};

/* ── status badge ──────────────────────────────────────────────────────── */

const STATUS_BADGES: Record<string, { label: string; className: string }> = {
  ACTIVE: {
    label: 'فعال',
    className:
      'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20',
  },
  PENDING: {
    label: 'در انتظار',
    className:
      'bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20',
  },
  ENDED: {
    label: 'پایان‌یافته',
    className: 'bg-muted text-muted-foreground border border-border',
  },
  REJECTED: {
    label: 'رد شده',
    className: 'bg-muted text-muted-foreground border border-border',
  },
};

function StatusBadge({ status }: { status: AdvisorStudent['status'] }) {
  const badge = STATUS_BADGES[status] ?? STATUS_BADGES.ENDED;
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${badge.className}`}
    >
      {badge.label}
    </span>
  );
}

/* ── adherence bar ─────────────────────────────────────────────────────── */

function adherenceBarClass(percent: number): string {
  if (percent >= 80) return 'bg-emerald-500';
  if (percent >= 50) return 'bg-amber-500';
  return 'bg-red-500';
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

type StatCardProps = {
  icon: LucideIcon;
  label: string;
  value: React.ReactNode;
  /** Optional trailing note under the value («نیاز به پیگیری» etc.). */
  hint?: string;
  valueClassName?: string;
  iconClassName?: string;
  href?: string;
};

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
  valueClassName,
  iconClassName,
  href,
}: StatCardProps) {
  const body = (
    <Card className="h-full border-border/50 transition-colors group-hover:border-primary/50 group-hover:bg-muted/40">
      <CardContent className="flex items-center gap-3 p-4">
        <span className={`shrink-0 rounded-lg p-2 ${iconClassName ?? 'bg-primary/10'}`}>
          <Icon className="h-4 w-4 text-primary" />
        </span>
        <div className="min-w-0">
          <p className="truncate text-xs text-muted-foreground">{label}</p>
          <p
            className={`mt-0.5 text-xl font-bold tabular-nums leading-none ${valueClassName ?? ''}`}
          >
            {value}
          </p>
          {hint && (
            <p className="mt-1 truncate text-[11px] font-medium text-muted-foreground">
              {hint}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );

  if (!href) return body;
  return (
    <Link href={href} className="group block h-full focus-visible:outline-none">
      {body}
    </Link>
  );
}

export type AdvisorStatStripProps = {
  activeStudents: number;
  pendingInvites: number;
  averageAdherence7d: number | null;
  activeChallengeCount: number;
};

/** The four headline counters of the advisor cockpit. */
export function AdvisorStatStrip({
  activeStudents,
  pendingInvites,
  averageAdherence7d,
  activeChallengeCount,
}: AdvisorStatStripProps) {
  const hasPending = pendingInvites > 0;
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatCard
        icon={Users}
        label="دانش‌آموزان فعال"
        value={toPersianDigits(activeStudents)}
      />
      <StatCard
        icon={UserPlus}
        label="در انتظار تأیید"
        value={toPersianDigits(pendingInvites)}
        hint={hasPending ? 'نیاز به پیگیری' : undefined}
        href="/advisor/students"
        iconClassName={
          hasPending ? 'bg-amber-500/10 ring-1 ring-amber-500/30' : undefined
        }
        valueClassName={
          hasPending ? 'text-amber-600 dark:text-amber-400' : undefined
        }
      />
      <StatCard
        icon={TrendingUp}
        label="میانگین تعهد ۷روزه"
        value={
          averageAdherence7d === null ? (
            '—'
          ) : (
            <span
              className={`rounded-md px-1.5 py-0.5 ${adherenceColorClass(averageAdherence7d)}`}
            >
              {formatPersianPercent(averageAdherence7d)}
            </span>
          )
        }
        hint={averageAdherence7d === null ? 'گزارشی ثبت نشده' : undefined}
      />
      <StatCard
        icon={Flame}
        label="چالش فعال"
        value={toPersianDigits(activeChallengeCount)}
      />
    </div>
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
      <Card className="flex h-full flex-col border-border/50 transition-colors hover:border-primary/50 hover:bg-muted/40">
        <CardContent className="flex h-full flex-col gap-3 p-4">
          <div className="flex items-start justify-between gap-2">
            <p className="min-w-0 truncate text-sm font-bold">{student.studentName}</p>
            <StatusBadge status={student.status} />
          </div>

          {adherence7d === null ? (
            <p className="text-xs leading-relaxed text-muted-foreground">
              برنامه‌ای این هفته نیست
            </p>
          ) : (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between gap-2 text-xs">
                <span className="text-muted-foreground">تعهد ۷روزه</span>
                <span
                  className={`rounded-full px-2 py-0.5 font-medium tabular-nums ${adherenceColorClass(adherence7d)}`}
                >
                  {formatPersianPercent(adherence7d)}
                </span>
              </div>
              <div
                role="progressbar"
                aria-valuenow={adherence7d}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`تعهد هفتگی ${student.studentName}`}
                className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
              >
                <div
                  className={`h-full rounded-full transition-all ${adherenceBarClass(adherence7d)}`}
                  style={{ width: `${Math.min(100, Math.max(0, adherence7d))}%` }}
                />
              </div>
            </div>
          )}

          <div className="mt-auto space-y-1.5 border-t border-border/40 pt-2.5">
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Clock className="h-3.5 w-3.5 shrink-0" />
              آخرین گزارش: {relativeLastLogLabel(lastLogDate)}
            </p>
            {activeChallengeTitle && (
              <p className="flex min-w-0 items-center gap-1.5 text-xs">
                <Target className="h-3.5 w-3.5 shrink-0 text-primary" />
                <span className="truncate" title={activeChallengeTitle}>
                  {activeChallengeTitle}
                </span>
              </p>
            )}
            <p className="flex items-center gap-1 pt-0.5 text-xs font-medium text-primary">
              مشاهده گزارش و برنامه
              <ArrowLeft className="h-3 w-3 transition-transform group-hover:-translate-x-0.5" />
            </p>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
