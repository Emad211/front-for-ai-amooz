'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import {
  Users,
  UserPlus,
  Clock,
  RefreshCw,
  AlertCircle,
  Send,
  Building2,
  FileText,
} from 'lucide-react';

import {
  AdvisoryService,
  type AdvisorStudent,
  type AdvisorPendingInvite,
} from '@/services/advisory-service';
import { toPersianDigits, toEnglishDigits } from '@/lib/persian-digits';
import { formatPersianDate } from '@/lib/date-utils';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { SubjectPickerDialog } from '@/components/advisory/subject-picker-dialog';

/**
 * Advisor → دانش‌آموزان من (roster + outbox + invite-by-phone).
 *
 * Three things on one screen because they are one job: who you already advise,
 * who you have invited and not heard back from, and the box to invite one more.
 *
 * The invite result is deliberately unhelpful about *who* the number belongs to.
 * The backend answers 202 for every well-formed number whether or not a student
 * owns it (a security property — see B2), so the success toast says "if this
 * number belongs to a student, we sent it", never "invited". Telling the advisor
 * more than that would turn their account into a phone→identity lookup for the
 * whole platform, which is the exact thing the uniform response prevents.
 */
export default function AdvisorStudentsPage() {
  const [students, setStudents] = useState<AdvisorStudent[] | null>(null);
  const [invites, setInvites] = useState<AdvisorPendingInvite[] | null>(null);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  const [phone, setPhone] = useState('');
  const [sending, setSending] = useState(false);

  useEffect(() => {
    let active = true;
    setError('');
    setStudents(null);
    setInvites(null);

    AdvisoryService.getStudents()
      .then((data) => {
        if (!active) return;
        setStudents(Array.isArray(data.students) ? data.students : []);
        setInvites(Array.isArray(data.pendingInvites) ? data.pendingInvites : []);
      })
      .catch((err: unknown) => {
        // Keep both lists null so the retry stays reachable and the screen never
        // claims "you have no students" when it simply failed to load.
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });

    return () => {
      active = false;
    };
  }, [reloadKey]);

  const submitInvite = async (event: React.FormEvent) => {
    event.preventDefault();
    // Canonicalize digits client-side so the payload is ASCII even when the
    // advisor typed Persian numerals; the backend normalizes again regardless.
    const value = toEnglishDigits(phone).replace(/\s+/g, '');
    if (!value) {
      toast.error('شماره‌ی موبایل را وارد کنید.');
      return;
    }

    setSending(true);
    try {
      await AdvisoryService.createInvite(value);
      // Intentionally does NOT confirm a student was found — the response is
      // uniform by design. Say only what is true for every branch.
      toast.success('اگر این شماره متعلق به دانش‌آموزی باشد، دعوت‌نامه برایش ارسال شد.');
      setPhone('');
      // Refetch so a newly created PENDING row shows up in the outbox. It only
      // appears when the number really is a registered student — which is fine:
      // the advisor typed the number, so the row leaks nothing they lacked.
      setReloadKey((k) => k + 1);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'ارسال دعوت‌نامه ناموفق بود.');
    } finally {
      setSending(false);
    }
  };

  const loading = !students && !invites && !error;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-bold sm:text-2xl">
          <Users className="h-5 w-5 text-primary" />
          دانش‌آموزان من
        </h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          دانش‌آموز را با شماره‌ی موبایلش دعوت کنید. همکاری وقتی آغاز می‌شود که
          دانش‌آموز دعوت را بپذیرد.
        </p>
      </div>

      {/* ── invite by phone ─────────────────────────────────────────────── */}
      <Card className="border-border/50">
        <CardContent className="py-4">
          <form onSubmit={submitInvite} className="space-y-2.5">
            <label
              htmlFor="advisor-invite-phone"
              className="flex items-center gap-1.5 text-sm font-medium"
            >
              <UserPlus className="h-4 w-4 text-primary" />
              دعوت دانش‌آموز تازه
            </label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                id="advisor-invite-phone"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="۰۹۱۲۳۴۵۶۷۸۹"
                inputMode="numeric"
                autoComplete="off"
                dir="ltr"
                className="text-left"
                disabled={sending}
                aria-label="شماره‌ی موبایل دانش‌آموز"
              />
              <Button type="submit" disabled={sending} className="shrink-0">
                <Send className="ml-2 h-4 w-4" />
                {sending ? 'در حال ارسال…' : 'ارسال دعوت'}
              </Button>
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              دانش‌آموز باید از قبل در سامانه ثبت‌نام کرده باشد. برای حفظ حریم
              خصوصی، نتیجه‌ی دعوت یکسان است و نشان نمی‌دهد شماره در سامانه هست یا نه.
            </p>
          </form>
        </CardContent>
      </Card>

      {/* ── loading ─────────────────────────────────────────────────────── */}
      {loading && (
        <div className="space-y-2" aria-busy="true" aria-live="polite">
          <span className="sr-only">در حال بارگذاری دانش‌آموزان…</span>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
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

      {/* ── roster ──────────────────────────────────────────────────────── */}
      {students && (
        <section className="space-y-2">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
            <Users className="h-4 w-4" />
            همکاری‌های فعال
            {students.length > 0 && (
              <Badge variant="secondary" className="font-normal">
                {toPersianDigits(students.length)}
              </Badge>
            )}
          </h2>

          {students.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="py-8 text-center">
                <Users className="mx-auto h-7 w-7 text-muted-foreground/60" />
                <p className="mt-2.5 text-sm font-medium">هنوز دانش‌آموز فعالی ندارید</p>
                <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-muted-foreground">
                  با ارسال دعوت‌نامه از کادر بالا شروع کنید. پس از پذیرش دانش‌آموز،
                  اینجا نمایش داده می‌شود.
                </p>
              </CardContent>
            </Card>
          ) : (
            <ul className="space-y-2">
              {students.map((s) => (
                <li key={s.id}>
                  <Card className="border-border/50">
                    <CardContent className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{s.studentName}</p>
                        <p dir="ltr" className="text-right text-xs text-muted-foreground">
                          {toPersianDigits(s.phoneMasked)}
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        {s.mode === 'org' && (
                          <Badge variant="outline" className="gap-1 font-normal">
                            <Building2 className="h-3 w-3" />
                            {s.organizationName || 'سازمانی'}
                          </Badge>
                        )}
                        {s.startedOn && (
                          <span className="text-xs text-muted-foreground">
                            از {formatPersianDate(s.startedOn)}
                          </span>
                        )}
                        <Button asChild variant="outline" size="sm">
                          <Link href={`/advisor/students/${s.id}`}>
                            <FileText className="ml-2 h-4 w-4" />
                            گزارش و برنامه
                          </Link>
                        </Button>
                        <SubjectPickerDialog
                          engagementId={s.id}
                          studentName={s.studentName}
                        />
                      </div>
                    </CardContent>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* ── outbox ──────────────────────────────────────────────────────── */}
      {invites && invites.length > 0 && (
        <section className="space-y-2">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
            <Clock className="h-4 w-4" />
            دعوت‌نامه‌های بی‌پاسخ
            <Badge variant="secondary" className="font-normal">
              {toPersianDigits(invites.length)}
            </Badge>
          </h2>
          <ul className="space-y-2">
            {invites.map((inv) => (
              <li key={inv.id}>
                <Card className="border-border/50">
                  <CardContent className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                    <div className="min-w-0">
                      <p dir="ltr" className="text-right text-sm font-medium">
                        {toPersianDigits(inv.phoneMasked)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        ارسال در {formatPersianDate(inv.invitedAt)}
                      </p>
                    </div>
                    {inv.isExpired ? (
                      <Badge variant="outline" className="font-normal text-muted-foreground">
                        منقضی شده
                      </Badge>
                    ) : (
                      <Badge variant="secondary" className="font-normal">
                        منتظر پاسخ
                      </Badge>
                    )}
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
