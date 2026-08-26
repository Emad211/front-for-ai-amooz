'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertCircle,
  CalendarDays,
  RefreshCw,
  UserPlus,
  Users,
} from 'lucide-react';

import { getStoredUser } from '@/services/auth-service';
import {
  AdvisoryService,
  type AdvisorOverviewResponse,
  type AdvisorOverviewStudentRow,
  type AdvisorStudentsResponse,
} from '@/services/advisory-service';
import { formatPersianDate } from '@/lib/date-utils';
import { toPersianDigits } from '@/lib/persian-digits';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  AdvisorStatStrip,
  AdvisorStudentCardView,
  type MergedAdvisorStudent,
} from '@/components/advisory/advisor-overview-cards';

/**
 * Advisor home cockpit.
 *
 * One screen answers "how are my students doing right now": headline counters,
 * then every student as a live card (7-day adherence, last report, active
 * challenge), sorted so struggling students surface first. The overview
 * endpoint is an enrichment layer — when it is slow or missing the roster
 * still renders, only quieter.
 */
export default function AdvisorHomePage() {
  const [name, setName] = useState('');
  // Computed client-side only: both touch localStorage / local time, which do
  // not exist during the server render pass.
  const [todayLabel, setTodayLabel] = useState('');

  const [roster, setRoster] = useState<AdvisorStudentsResponse | null>(null);
  const [overview, setOverview] = useState<AdvisorOverviewResponse | null>(null);
  const [rosterError, setRosterError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const user = getStoredUser();
    const full = [user?.first_name, user?.last_name].filter(Boolean).join(' ').trim();
    setName(full || user?.username || '');
    setTodayLabel(formatPersianDate(new Date()));
  }, []);

  useEffect(() => {
    let active = true;
    setRoster(null);
    setOverview(null);
    setRosterError('');

    // Both calls run independently on purpose: a failed/slow overview must
    // never take the roster down with it (the cockpit degrades, not breaks).
    AdvisoryService.getStudents()
      .then((data) => {
        if (!active) return;
        setRoster({
          students: Array.isArray(data.students) ? data.students : [],
          pendingInvites: Array.isArray(data.pendingInvites)
            ? data.pendingInvites
            : [],
          folders: Array.isArray(data.folders) ? data.folders : [],
        });
      })
      .catch((err: unknown) => {
        if (!active) return;
        // Roster shape stays non-null so the section renders; the error card
        // below explains what happened and offers the retry.
        setRoster({ students: [], pendingInvites: [], folders: [] });
        setRosterError(err instanceof Error ? err.message : 'خطای نامشخص');
      });

    AdvisoryService.getAdvisorOverview()
      .then((data) => {
        if (active) setOverview(data);
      })
      .catch(() => {
        // Quiet by design: the roster renders unenriched instead.
      });

    return () => {
      active = false;
    };
  }, [reloadKey]);

  const merged = useMemo<MergedAdvisorStudent[]>(() => {
    if (!roster) return [];
    const byEngagement = new Map<number, AdvisorOverviewStudentRow>();
    for (const row of overview?.students ?? []) {
      if (row && Number.isFinite(row.engagementId)) {
        byEngagement.set(Number(row.engagementId), row);
      }
    }
    const list = roster.students.map((student) => {
      const row = byEngagement.get(Number(student.id));
      return {
        student,
        adherence7d: row?.adherence7d ?? null,
        lastLogDate: row?.lastLogDate ?? null,
        activeChallengeTitle: row?.activeChallengeTitle ?? null,
      };
    });
    // ACTIVE first, and within them the lowest adherence on top — the
    // struggling student is the one the advisor needs to see first. Nulls
    // sort after known values inside each group.
    const isActive = (s: MergedAdvisorStudent) => s.student.status === 'ACTIVE';
    list.sort((a, b) => {
      const groupDiff = Number(isActive(b)) - Number(isActive(a));
      if (groupDiff !== 0) return groupDiff;
      if (isActive(a)) {
        if (a.adherence7d === null && b.adherence7d !== null) return 1;
        if (b.adherence7d === null && a.adherence7d !== null) return -1;
        if (a.adherence7d !== null && b.adherence7d !== null) {
          return a.adherence7d - b.adherence7d;
        }
      }
      return 0;
    });
    return list;
  }, [roster, overview]);

  const loading = !roster && !rosterError;

  // Prefer server metrics; fall back to what the roster alone can prove so
  // the strip never lies just because the overview call failed.
  const activeStudents =
    overview?.metrics?.activeStudents ??
    (roster?.students ?? []).filter((s) => s.status === 'ACTIVE').length;
  const pendingInvites =
    overview?.metrics?.pendingInvites ?? (roster?.pendingInvites.length ?? 0);
  const averageAdherence7d = overview?.metrics?.averageAdherence7d ?? null;
  const activeChallengeCount = merged.filter(
    (m) => m.activeChallengeTitle !== null,
  ).length;

  const hasStudents = (roster?.students.length ?? 0) > 0;

  return (
    <div className="space-y-5">
      {/* ── header ─────────────────────────────────────────────────────── */}
      <div>
        <h1 className="text-xl font-bold sm:text-2xl">
          {name ? `${name} عزیز، خوش آمدید` : 'خوش آمدید'}
        </h1>
        <p className="mt-1.5 flex items-center gap-1.5 text-xs text-muted-foreground sm:text-sm">
          <CalendarDays className="h-3.5 w-3.5 shrink-0" />
          {todayLabel}
        </p>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground sm:text-sm">
          نگاهی به وضعیت امروز دانش‌آموزانتان: تعهد هفتگی، آخرین گزارش‌ها و
          چالش‌های در جریان.
        </p>
      </div>

      {/* ── stat strip ─────────────────────────────────────────────────── */}
      {loading ? (
        <div aria-busy="true" aria-live="polite">
          <span className="sr-only">در حال بارگذاری نمای کلی…</span>
          <Skeleton className="h-20 rounded-2xl" />
        </div>
      ) : (
        <AdvisorStatStrip
          activeStudents={activeStudents}
          pendingInvites={pendingInvites}
          averageAdherence7d={averageAdherence7d}
          activeChallengeCount={activeChallengeCount}
        />
      )}

      {/* ── roster load failure ────────────────────────────────────────── */}
      {!loading && rosterError && (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
            <p className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {rosterError}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setReloadKey((k) => k + 1)}
            >
              <RefreshCw className="ml-2 h-4 w-4" />
              تلاش مجدد
            </Button>
          </CardContent>
        </Card>
      )}

      {/* ── students ───────────────────────────────────────────────────── */}
      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
          <Users className="h-4 w-4" />
          دانش‌آموزان من
          {hasStudents && (
            <Badge variant="secondary" className="font-normal tabular-nums">
              {toPersianDigits(roster?.students.length ?? 0)}
            </Badge>
          )}
        </h2>

        {loading && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-40 rounded-2xl" />
            ))}
          </div>
        )}

        {!loading && !hasStudents && (
          <Card className="border-border/50">
            <CardContent className="py-12 text-center">
              <UserPlus className="mx-auto h-7 w-7 text-muted-foreground" />
              <p className="mt-3 text-sm font-bold">اولین دانش‌آموزت را دعوت کن</p>
              <p className="mx-auto mt-1.5 max-w-md text-xs leading-relaxed text-muted-foreground">
                با ارسال یک دعوت‌نامه شروع کنید؛ پس از پذیرش دانش‌آموز، گزارش
                مطالعه و برنامهٔ هفتگی‌اش همین‌جا زنده می‌شود.
              </p>
              <Button asChild size="sm" className="mt-4">
                <Link href="/advisor/students">
                  <UserPlus className="ml-2 h-4 w-4" />
                  دعوت دانش‌آموز
                </Link>
              </Button>
            </CardContent>
          </Card>
        )}

        {!loading && hasStudents && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {merged.map((entry) => (
              <AdvisorStudentCardView key={entry.student.id} entry={entry} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

