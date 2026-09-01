'use client';

import { useEffect, useMemo, useState } from 'react';
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
  Search,
  FolderOpen,
  FolderPlus,
  Pencil,
  Trash2,
  X,
  Check,
} from 'lucide-react';

import {
  AdvisoryService,
  type AdvisorStudent,
  type AdvisorPendingInvite,
  type AdvisorFolder,
  type AdvisorOverviewResponse,
} from '@/services/advisory-service';
import { toPersianDigits, toEnglishDigits } from '@/lib/persian-digits';
import { adherenceColorClass, formatAdherence } from '@/lib/adherence';
import { formatPersianDate } from '@/lib/date-utils';
import { relativeLastLogLabel } from '@/components/advisory/advisor-overview-cards';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { SubjectPickerDialog } from '@/components/advisory/subject-picker-dialog';

type RosterRow = {
  student: AdvisorStudent;
  adherence7d: number | null;
  lastLogDate: string | null;
};

/** Whole days since an ISO log date; null = absent/unparseable (unknown ≠ 0). */
function daysSinceLastLog(iso: string | null): number | null {
  if (!iso) return null;
  const then = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(then.getTime())) return null;
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((startOfToday.getTime() - then.getTime()) / 86_400_000);
}

/** Roster twin of the cockpit's label, worded «بی‌گزارش» instead of «هرگز». */
function rosterLastLogLabel(lastLogDate: string | null): string {
  if (daysSinceLastLog(lastLogDate) === null) return 'بی‌گزارش';
  return relativeLastLogLabel(lastLogDate);
}

/** Non-ACTIVE roster statuses get one calm outline badge; ACTIVE (the default
 * reading) stays bare. Labels mirror the cockpit's STATUS_DOTS wording. */
const ROSTER_STATUS_BADGE: Partial<
  Record<AdvisorStudent['status'], { label: string; className: string }>
> = {
  PENDING: {
    label: 'در انتظار پذیرش',
    className: 'border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-400',
  },
  ENDED: { label: 'پایان‌یافته', className: 'text-muted-foreground' },
  REJECTED: { label: 'رد شده', className: 'text-muted-foreground' },
};

/** Triage rule: no report for ≥3 days (or no report at all) OR weekly
 * execution under 50%; unknown adherence alone never flags a student. */
function needsFollowUp(adherence7d: number | null, lastLogDate: string | null): boolean {
  if (adherence7d !== null && adherence7d < 50) return true;
  const days = daysSinceLastLog(lastLogDate);
  return days === null || days >= 3;
}

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
 *
 * Risman step 1 adds the search bar (300ms debounce → `?q=`) and the folder
 * chips + per-student move-to-folder select (`?folder=` / PATCH …/folder/).
 */
export default function AdvisorStudentsPage() {
  const [students, setStudents] = useState<AdvisorStudent[] | null>(null);
  const [invites, setInvites] = useState<AdvisorPendingInvite[] | null>(null);
  const [folders, setFolders] = useState<AdvisorFolder[]>([]);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  const [overview, setOverview] = useState<AdvisorOverviewResponse | null>(null);
  const [lowestExecutionFirst, setLowestExecutionFirst] = useState(true);
  const [onlyNeedsFollowUp, setOnlyNeedsFollowUp] = useState(false);

  const [phone, setPhone] = useState('');
  const [sending, setSending] = useState(false);

  // Risman step 1: search (debounced) + active folder chip drive the refetch.
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [activeFolderId, setActiveFolderId] = useState<number | null>(null);

  // Inline folder management (create / rename / delete).
  const [manageOpen, setManageOpen] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingName, setEditingName] = useState('');
  const [folderBusy, setFolderBusy] = useState(false);

  const [movingId, setMovingId] = useState<number | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setQuery(searchInput.trim()), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    let active = true;
    setError('');
    setStudents(null);
    setInvites(null);

    AdvisoryService.getStudents({
      q: query || undefined,
      folderId: activeFolderId ?? undefined,
    })
      .then((data) => {
        if (!active) return;
        setStudents(Array.isArray(data.students) ? data.students : []);
        setInvites(Array.isArray(data.pendingInvites) ? data.pendingInvites : []);
        setFolders(Array.isArray(data.folders) ? data.folders : []);
      })
      .catch((err: unknown) => {
        // Keep both lists null so the retry stays reachable and the screen never
        // claims "you have no students" when it simply failed to load.
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });

    return () => {
      active = false;
    };
  }, [reloadKey, query, activeFolderId]);

  useEffect(() => {
    let active = true;
    AdvisoryService.getAdvisorOverview()
      .then((data) => {
        if (active) setOverview(data);
      })
      .catch(() => {
        // Silent by design: the roster renders unenriched instead.
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
      toast.error('شمارهٔ موبایل را وارد کنید.');
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

  const moveToFolder = async (engagementId: number, rawValue: string) => {
    const folderId = rawValue === 'none' ? null : Number(rawValue);
    setMovingId(engagementId);
    try {
      await AdvisoryService.setStudentFolder(engagementId, folderId);
      toast.success('جای دانش‌آموز به‌روزرسانی شد.');
      setReloadKey((k) => k + 1);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'انتقال ناموفق بود.');
    } finally {
      setMovingId(null);
    }
  };

  const submitCreateFolder = async (event: React.FormEvent) => {
    event.preventDefault();
    const name = newFolderName.trim();
    if (!name) {
      toast.error('نام پوشه الزامی است.');
      return;
    }
    setCreating(true);
    try {
      const created = await AdvisoryService.createFolder(name);
      setFolders((prev) =>
        [...prev, created].sort((a, b) => a.name.localeCompare(b.name, 'fa')),
      );
      setNewFolderName('');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'ساخت پوشه ناموفق بود.');
    } finally {
      setCreating(false);
    }
  };

  const startRename = (folder: AdvisorFolder) => {
    setEditingId(folder.id);
    setEditingName(folder.name);
  };

  const submitRename = async () => {
    if (editingId == null) return;
    const name = editingName.trim();
    if (!name) {
      toast.error('نام پوشه الزامی است.');
      return;
    }
    setFolderBusy(true);
    try {
      const saved = await AdvisoryService.renameFolder(editingId, name);
      setFolders((prev) =>
        prev
          .map((f) => (f.id === saved.id ? saved : f))
          .sort((a, b) => a.name.localeCompare(b.name, 'fa')),
      );
      setEditingId(null);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'تغییر نام ناموفق بود.');
    } finally {
      setFolderBusy(false);
    }
  };

  const submitDeleteFolder = async (folder: AdvisorFolder) => {
    if (
      !window.confirm(
        `پوشهٔ «${folder.name}» حذف شود؟ دانش‌آموزان داخل آن حذف نمی‌شوند و بدون پوشه می‌مانند.`,
      )
    ) {
      return;
    }
    setFolderBusy(true);
    try {
      await AdvisoryService.deleteFolder(folder.id);
      setFolders((prev) => prev.filter((f) => f.id !== folder.id));
      // Deleting nulls the roster's folderIds server-side — refetch so the
      // rows stop claiming membership in a folder that no longer exists.
      if (activeFolderId === folder.id) setActiveFolderId(null);
      setReloadKey((k) => k + 1);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'حذف پوشه ناموفق بود.');
    } finally {
      setFolderBusy(false);
    }
  };

  const loading = !students && !invites && !error;
  const filtering =
    query !== '' || activeFolderId !== null || onlyNeedsFollowUp;
  const overviewReady = overview !== null;

  const rosterRows = useMemo<RosterRow[]>(() => {
    if (!students) return [];
    const byEngagement = new Map<number, AdvisorOverviewResponse['students'][number]>();
    for (const row of overview?.students ?? []) {
      if (row && Number.isFinite(row.engagementId)) {
        byEngagement.set(Number(row.engagementId), row);
      }
    }
    let list: RosterRow[] = students.map((student) => {
      const row = overviewReady ? byEngagement.get(Number(student.id)) : undefined;
      return {
        student,
        adherence7d: row?.adherence7d ?? null,
        lastLogDate: row?.lastLogDate ?? null,
      };
    });
    // Without overview data the triage rule would flag everyone — skip it.
    if (onlyNeedsFollowUp && overviewReady) {
      list = list.filter((row) => needsFollowUp(row.adherence7d, row.lastLogDate));
    }
    if (lowestExecutionFirst) {
      list = [...list].sort((a, b) => {
        if (a.adherence7d === null && b.adherence7d === null) return 0;
        if (a.adherence7d === null) return 1;
        if (b.adherence7d === null) return -1;
        return a.adherence7d - b.adherence7d;
      });
    }
    return list;
  }, [students, overview, overviewReady, onlyNeedsFollowUp, lowestExecutionFirst]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-bold sm:text-2xl">
          <Users className="h-5 w-5 text-primary" />
          دانش‌آموزان من
        </h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          دانش‌آموز را با شمارهٔ موبایلش دعوت کنید. همکاری وقتی آغاز می‌شود که
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
                aria-label="شمارهٔ موبایل دانش‌آموز"
              />
              <Button type="submit" disabled={sending} className="shrink-0">
                <Send className="ml-2 h-4 w-4" />
                {sending ? 'در حال ارسال…' : 'ارسال دعوت'}
              </Button>
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              دانش‌آموز باید از قبل در سامانه ثبت‌نام کرده باشد. برای حفظ حریم
              خصوصی، نتیجهٔ دعوت یکسان است و نشان نمی‌دهد شماره در سامانه هست یا نه.
            </p>
          </form>
        </CardContent>
      </Card>

      {/* ── risman step 1: search + folder chips ────────────────────────── */}
      <div className="space-y-2.5">
        <div className="relative">
          <Search className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="جستجو بر اساس نام، نام کاربری یا شماره…"
            className="pr-9"
            aria-label="جستجوی دانش‌آموز"
          />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Button
            variant={activeFolderId === null ? 'default' : 'outline'}
            size="sm"
            className="h-7 rounded-full px-3 text-xs"
            onClick={() => setActiveFolderId(null)}
          >
            همه
          </Button>
          {folders.map((f) => (
            <Button
              key={f.id}
              variant={activeFolderId === f.id ? 'default' : 'outline'}
              size="sm"
              className="h-7 max-w-48 rounded-full px-3 text-xs"
              onClick={() =>
                setActiveFolderId((current) => (current === f.id ? null : f.id))
              }
            >
              <span className="truncate">{f.name}</span>
            </Button>
          ))}
          <Button
            variant="ghost"
            size="sm"
            className="h-7 rounded-full px-3 text-xs text-muted-foreground"
            onClick={() => setManageOpen(true)}
          >
            <FolderOpen className="ml-1 h-3.5 w-3.5" />
            مدیریت پوشه‌ها
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant={lowestExecutionFirst ? 'default' : 'outline'}
            size="sm"
            className="h-11 rounded-full px-4"
            aria-pressed={lowestExecutionFirst}
            onClick={() => setLowestExecutionFirst((v) => !v)}
          >
            کمترین اجرا اول
          </Button>
          <Button
            variant={onlyNeedsFollowUp ? 'default' : 'outline'}
            size="sm"
            className="h-11 rounded-full px-4"
            aria-pressed={onlyNeedsFollowUp}
            onClick={() => setOnlyNeedsFollowUp((v) => !v)}
          >
            نیازمند پیگیری
          </Button>
          {overviewReady && onlyNeedsFollowUp && (
            <span className="text-xs text-muted-foreground">
              بی‌گزارش یا اجرای زیر ۵۰٪
            </span>
          )}
        </div>
      </div>

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
            دانش‌آموزان من
            {rosterRows.length > 0 && (
              <Badge variant="secondary" className="font-normal">
                {toPersianDigits(rosterRows.length)}
              </Badge>
            )}
          </h2>

          {rosterRows.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="py-8 text-center">
                <Users className="mx-auto h-7 w-7 text-muted-foreground/60" />
                {filtering ? (
                  <>
                    <p className="mt-2.5 text-sm font-medium">دانش‌آموزی پیدا نشد</p>
                    <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-muted-foreground">
                      عبارت جستجو یا فیلترهای انتخاب‌شده را تغییر دهید.
                    </p>
                  </>
                ) : (
                  <>
                    <p className="mt-2.5 text-sm font-medium">هنوز دانش‌آموز فعالی ندارید</p>
                    <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-muted-foreground">
                      با ارسال دعوت‌نامه از کادر بالا شروع کنید. پس از پذیرش دانش‌آموز،
                      اینجا نمایش داده می‌شود.
                    </p>
                  </>
                )}
              </CardContent>
            </Card>
          ) : (
            <ul className="space-y-2">
              {rosterRows.map(({ student: s, adherence7d, lastLogDate }) => {
                const statusBadge = ROSTER_STATUS_BADGE[s.status];
                return (
                <li key={s.id}>
                  <Card className="border-border/50">
                    <CardContent className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="min-w-0 truncate text-sm font-medium">{s.studentName}</p>
                          {statusBadge && (
                            <Badge
                              variant="outline"
                              className={`shrink-0 text-[11px] font-normal ${statusBadge.className}`}
                            >
                              {statusBadge.label}
                            </Badge>
                          )}
                        </div>
                        <p dir="ltr" className="text-right text-xs text-muted-foreground">
                          {toPersianDigits(s.phoneMasked)}
                        </p>
                        {overviewReady && (
                          <p className="mt-0.5 text-xs text-muted-foreground">
                            آخرین گزارش: {rosterLastLogLabel(lastLogDate)}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        {adherence7d !== null && (
                          <Badge
                            variant="outline"
                            className={`text-[11px] font-normal tabular-nums ${adherenceColorClass(adherence7d)}`}
                            title="درصد اجرای برنامهٔ ۷ روز گذشته"
                          >
                            اجرا {formatAdherence(adherence7d)}
                          </Badge>
                        )}
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
                        <Select
                          value={s.folderId == null ? 'none' : String(s.folderId)}
                          onValueChange={(value) => moveToFolder(s.id, value)}
                          disabled={movingId === s.id}
                        >
                          <SelectTrigger
                            className="h-8 w-36 text-xs"
                            aria-label={`انتقال ${s.studentName} به پوشه`}
                          >
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="none">بدون پوشه</SelectItem>
                            {folders.map((f) => (
                              <SelectItem key={f.id} value={String(f.id)}>
                                {f.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
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
                );
              })}
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

      {/* ── folder management dialog ────────────────────────────────────── */}
      <Dialog open={manageOpen} onOpenChange={(open) => {
        setManageOpen(open);
        if (!open) setEditingId(null);
      }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FolderOpen className="h-4 w-4 text-primary" />
              مدیریت پوشه‌ها
            </DialogTitle>
            <DialogDescription>
              پوشه‌ها فقط برای خودتان دیده می‌شوند و راهی برای دسته‌بندی
              دانش‌آموزان‌اند.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={submitCreateFolder} className="flex gap-2">
            <Input
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="نام پوشهٔ تازه"
              maxLength={64}
              aria-label="نام پوشهٔ تازه"
            />
            <Button type="submit" disabled={creating} className="shrink-0">
              <FolderPlus className="ml-1 h-4 w-4" />
              افزودن
            </Button>
          </form>

          <ul className="max-h-60 space-y-1.5 overflow-y-auto">
            {folders.map((f) =>
              editingId === f.id ? (
                <li key={f.id} className="flex gap-1.5">
                  <Input
                    value={editingName}
                    onChange={(e) => setEditingName(e.target.value)}
                    maxLength={64}
                    autoFocus
                    aria-label={`نام تازه برای ${f.name}`}
                  />
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-9 w-9 shrink-0"
                    onClick={submitRename}
                    disabled={folderBusy}
                    aria-label="ذخیرهٔ نام تازه"
                  >
                    <Check className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 shrink-0"
                    onClick={() => setEditingId(null)}
                    aria-label="انصراف"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </li>
              ) : (
                <li
                  key={f.id}
                  className="flex items-center justify-between rounded-md border border-border/50 px-3 py-2"
                >
                  <span className="min-w-0 truncate text-sm">{f.name}</span>
                  <span className="flex shrink-0 gap-0.5">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => startRename(f)}
                      aria-label={`تغییر نام ${f.name}`}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive hover:text-destructive"
                      onClick={() => submitDeleteFolder(f)}
                      disabled={folderBusy}
                      aria-label={`حذف ${f.name}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </span>
                </li>
              ),
            )}
            {folders.length === 0 && (
              <li className="py-4 text-center text-xs text-muted-foreground">
                هنوز پوشه‌ای نساخته‌اید.
              </li>
            )}
          </ul>
        </DialogContent>
      </Dialog>
    </div>
  );
}
