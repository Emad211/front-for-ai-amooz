'use client';

import { useEffect, useMemo, useState } from 'react';
import { BookOpen, RefreshCw, Search, AlertCircle } from 'lucide-react';

import { AdvisoryService, type AdvisorySubject } from '@/services/advisory-service';
import { matchesSearch } from '@/lib/persian-search';
import { toPersianDigits } from '@/lib/persian-digits';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

/**
 * Advisor → درس‌ها (subject catalog), read-only.
 *
 * The advisor does not create subjects: the platform admin curates the shared
 * national catalog and an organization curates its own private additions. This
 * page is a read-only view of that full catalog — what an advisor can actually
 * *focus* for a given student is derived per-student from that student's own grade
 * and major (the per-student picker), so this is a reference list, not that picker.
 * It also makes a missing subject a visible, reportable fact rather than a silently
 * short picker.
 *
 * Filtering is client-side because the endpoint is unpaginated by design: the
 * whole catalog is already in hand, so a round-trip per keystroke would be
 * slower and would add a failure mode for nothing.
 */
export default function AdvisorSubjectsPage() {
  const [subjects, setSubjects] = useState<AdvisorySubject[] | null>(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [gradeFilter, setGradeFilter] = useState('all');
  const [majorFilter, setMajorFilter] = useState('all');
  const [nameFilter, setNameFilter] = useState('all');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    setError('');
    setSubjects(null);

    AdvisoryService.getSubjects()
      .then((rows) => {
        if (active) setSubjects(rows);
      })
      .catch((err: unknown) => {
        // Keep `subjects` null so the retry button stays reachable: an empty
        // array here would render as "the catalog is empty", which is a
        // different and much more misleading statement than "load failed".
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });

    return () => {
      active = false;
    };
  }, [reloadKey]);

  const gradeOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const s of subjects ?? []) {
      if (s.grade && !seen.has(s.grade)) seen.set(s.grade, s.gradeLabel ?? s.grade);
    }
    return [...seen.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([value, label]) => ({ value, label }));
  }, [subjects]);

  const majorOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const s of subjects ?? []) {
      const key = s.major ?? 'general';
      if (!seen.has(key)) seen.set(key, s.majorLabel ?? 'مشترک (همهٔ رشته‌ها)');
    }
    return [...seen.entries()].map(([value, label]) => ({ value, label }));
  }, [subjects]);

  const nameOptions = useMemo(() => {
    const seen = new Set<string>();
    for (const s of subjects ?? []) seen.add(s.name);
    return [...seen].sort((a, b) => a.localeCompare(b, 'fa'));
  }, [subjects]);

  const visible = useMemo(
    () =>
      (subjects ?? []).filter(
        (s) =>
          (gradeFilter === 'all' || s.grade === gradeFilter) &&
          (majorFilter === 'all' || (s.major ?? 'general') === majorFilter) &&
          (nameFilter === 'all' || s.name === nameFilter) &&
          matchesSearch(s.name, query),
      ),
    [subjects, gradeFilter, majorFilter, nameFilter, query],
  );

  const filtersActive =
    query.trim() !== '' ||
    gradeFilter !== 'all' ||
    majorFilter !== 'all' ||
    nameFilter !== 'all';

  const globalCount = (subjects ?? []).filter((s) => s.isGlobal).length;
  const orgCount = (subjects ?? []).length - globalCount;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold sm:text-2xl">
            <BookOpen className="h-5 w-5 text-primary" />
            درس‌ها
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            کاتالوگِ کاملِ درس‌ها. برنامهٔ هر دانش‌آموز از پایه و رشتهٔ خودش
            ساخته می‌شود؛ اینجا فقط فهرست را می‌بینید.
          </p>
        </div>
        {subjects && subjects.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="secondary">
              {toPersianDigits(globalCount)} درس سراسری
            </Badge>
            {orgCount > 0 && (
              <Badge variant="outline">
                {toPersianDigits(orgCount)} درس سازمانی
              </Badge>
            )}
          </div>
        )}
      </div>

      {/* ── loading ─────────────────────────────────────────────────────── */}
      {!subjects && !error && (
        <div className="space-y-2" aria-busy="true" aria-live="polite">
          <span className="sr-only">در حال بارگذاری درس‌ها…</span>
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      )}

      {/* ── load failure ────────────────────────────────────────────────── */}
      {error && (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
            <p className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
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

      {/* ── catalog genuinely empty ─────────────────────────────────────── */}
      {subjects && subjects.length === 0 && (
        <Card className="border-dashed">
          <CardContent className="py-10 text-center">
            <BookOpen className="mx-auto h-8 w-8 text-muted-foreground/60" />
            <p className="mt-3 text-sm font-medium">هنوز درسی ثبت نشده است</p>
            <p className="mx-auto mt-1.5 max-w-md text-xs leading-relaxed text-muted-foreground">
              فهرست درس‌ها را مدیر پلتفرم (برای همه) یا سازمان آموزشی شما (فقط
              برای خودش) تنظیم می‌کند. اگر درسی را لازم دارید و اینجا نیست، به
              پشتیبانی اطلاع دهید.
            </p>
          </CardContent>
        </Card>
      )}

      {/* ── the catalog ─────────────────────────────────────────────────── */}
      {subjects && subjects.length > 0 && (
        <>
          <div className="grid gap-2 sm:grid-cols-3">
            <Select value={gradeFilter} onValueChange={setGradeFilter}>
              <SelectTrigger aria-label="فیلتر پایه" className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">همهٔ پایه‌ها</SelectItem>
                {gradeOptions.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={majorFilter} onValueChange={setMajorFilter}>
              <SelectTrigger aria-label="فیلتر رشته" className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">همهٔ رشته‌ها</SelectItem>
                {majorOptions.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={nameFilter} onValueChange={setNameFilter}>
              <SelectTrigger aria-label="فیلتر زیرشاخه" className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">همهٔ زیرشاخه‌ها</SelectItem>
                {nameOptions.map((n) => (
                  <SelectItem key={n} value={n}>
                    {n}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="relative">
            <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="جست‌وجوی نام درس…"
              className="pr-9"
              aria-label="جست‌وجوی نام درس"
            />
          </div>

          {visible.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              درسی با این فیلترها پیدا نشد.
            </p>
          ) : (
            <ul className="space-y-2">
              {visible.map((subject) => (
                <li key={subject.id}>
                  <Card className="border-border/50">
                    <CardContent className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                      <div className="flex min-w-0 flex-wrap items-center gap-2">
                        <span className="truncate text-sm font-medium">
                          {subject.name}
                        </span>
                        {subject.gradeLabel && (
                          <Badge variant="secondary" className="font-normal">
                            {subject.gradeLabel}
                          </Badge>
                        )}
                        {subject.majorLabel && (
                          <Badge variant="outline" className="font-normal">
                            {subject.majorLabel}
                          </Badge>
                        )}
                      </div>
                      {subject.isGlobal ? (
                        <Badge variant="secondary" className="font-normal">
                          سراسری
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="font-normal">
                          {subject.organizationName || 'سازمانی'}
                        </Badge>
                      )}
                    </CardContent>
                  </Card>
                </li>
              ))}
            </ul>
          )}

          {filtersActive && visible.length > 0 && (
            <p className="text-center text-xs text-muted-foreground">
              {toPersianDigits(visible.length)} از {toPersianDigits(subjects.length)} درس
            </p>
          )}
        </>
      )}
    </div>
  );
}
