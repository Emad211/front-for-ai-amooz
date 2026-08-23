'use client';

import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { BookOpen, Search, AlertCircle, Building2, Loader2 } from 'lucide-react';

import {
  AdvisoryService,
  type AdvisorySubject,
} from '@/services/advisory-service';
import { matchesSearch } from '@/lib/persian-search';
import { toPersianDigits } from '@/lib/persian-digits';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';

/**
 * The advisor's per-student subject picker.
 *
 * A set-replace, not a checklist you save row by row: the advisor ticks the whole
 * set and «ذخیره» sends it once, so the student's subjects only ever change on a
 * deliberate save. Everything is loaded fresh on each open — the current selection
 * can have moved since last time.
 *
 * The candidate list is the student's **derived curriculum**: the server computes it
 * from the student's own `(grade, major)` and returns it as `subjects`, so this
 * dialog neither knows nor re-implements the derivation rule. There is no grade
 * filter any more — the whole list already belongs to this one student's grade and
 * major, so the only narrowing left is a text search to find a row quickly.
 */
type SubjectPickerDialogProps = {
  /** The ENGAGEMENT id (`AdvisorStudent.id`), never the student's user id. */
  engagementId: number;
  studentName: string;
};

export function SubjectPickerDialog({
  engagementId,
  studentName,
}: SubjectPickerDialogProps) {
  const [open, setOpen] = useState(false);
  const [catalog, setCatalog] = useState<AdvisorySubject[] | null>(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  // The student's own axes, echoed back by the GET purely for the header: they let
  // the advisor see *why* this candidate set, and tell an empty-because-no-grade
  // apart from an empty-because-no-catalog. `studentGrade === null` ⇒ the student
  // has not set a grade, so the server derived nothing.
  const [studentGrade, setStudentGrade] = useState<string | null>(null);
  const [studentAxisLabel, setStudentAxisLabel] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);

  // One call on each open: the derived curriculum, the current selection, and the
  // student's axes for the header all arrive together. The candidate set is computed
  // server-side, so there is nothing to merge or filter here.
  useEffect(() => {
    if (!open) return;
    let active = true;
    setError('');
    setCatalog(null);
    setQuery('');

    AdvisoryService.getEngagementSubjects(engagementId)
      .then((resp) => {
        if (!active) return;
        setCatalog(Array.isArray(resp.subjects) ? resp.subjects : []);
        setSelected(
          new Set(Array.isArray(resp.selectedSubjectIds) ? resp.selectedSubjectIds : []),
        );
        setStudentGrade(resp.studentGrade);
        setStudentAxisLabel(
          [resp.studentGradeLabel, resp.studentMajorLabel]
            .filter(Boolean)
            .join(' · '),
        );
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'خطای نامشخص');
      });

    return () => {
      active = false;
    };
  }, [open, engagementId]);

  const visible = useMemo(() => {
    if (!catalog) return [];
    // Search-only: the whole candidate set already belongs to this student's grade
    // and major (the server derived it), so there is nothing more to gate on.
    return catalog.filter((s) => matchesSearch(s.name, query));
  }, [catalog, query]);

  const toggleSubject = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const save = async () => {
    setSaving(true);
    try {
      await AdvisoryService.setEngagementSubjects(engagementId, [...selected]);
      toast.success(`درس‌های «${studentName}» ذخیره شد.`);
      setOpen(false);
    } catch (err: unknown) {
      // 409 (engagement not active) and 400 (subject not assignable) surface their
      // Persian detail here; the advisor learns why without a status code.
      toast.error(err instanceof Error ? err.message : 'ذخیره‌ی درس‌ها ناموفق بود.');
    } finally {
      setSaving(false);
    }
  };

  const loading = open && !catalog && !error;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="shrink-0">
          <BookOpen className="ml-2 h-4 w-4" />
          انتخاب درس‌ها
        </Button>
      </DialogTrigger>

      <DialogContent
        dir="rtl"
        className="flex max-h-[85vh] flex-col gap-0 p-0 sm:max-w-lg"
      >
        <DialogHeader className="space-y-1 px-5 pt-5 text-right">
          <DialogTitle className="flex flex-wrap items-center gap-2 text-base">
            <BookOpen className="h-4 w-4 text-primary" />
            درس‌های «{studentName}»
            {studentAxisLabel && (
              <Badge variant="secondary" className="font-normal">
                {studentAxisLabel}
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription className="text-xs leading-relaxed">
            از برنامه‌ی درسیِ این دانش‌آموز، درس‌هایی را که می‌خواهید روی آن‌ها
            تمرکز شود انتخاب کنید و «ذخیره» بزنید. هرچه انتخاب نشود کنار گذاشته
            می‌شود.
          </DialogDescription>
        </DialogHeader>

        {/* search — fixed above the scrolling list */}
        <div className="shrink-0 px-5 pt-3">
          <div className="relative">
            <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="جستجوی درس…"
              className="pr-9"
              aria-label="جستجوی درس"
              disabled={loading || !!error}
            />
          </div>
        </div>

        {/* the list */}
        <ScrollArea className="mt-3 flex-1 border-t">
          <div className="px-3 py-2">
            {loading && (
              <div className="space-y-1.5" aria-busy="true">
                {[0, 1, 2, 3, 4].map((i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            )}

            {error && (
              <p className="flex items-center gap-2 px-2 py-6 text-sm text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {error}
              </p>
            )}

            {catalog && !error && visible.length === 0 && (
              <p className="px-2 py-8 text-center text-sm leading-relaxed text-muted-foreground">
                {catalog.length === 0
                  ? studentGrade === null
                    ? 'تا وقتی دانش‌آموز پایه‌اش را در پروفایل ثبت نکند، برنامه‌ی درسی‌ای برای انتخاب نیست.'
                    : 'برای این پایه و رشته هنوز درسی در برنامه ثبت نشده است.'
                  : 'درسی با این جستجو پیدا نشد.'}
              </p>
            )}

            {catalog &&
              !error &&
              visible.map((s) => {
                const checked = selected.has(s.id);
                return (
                  <button
                    key={s.id}
                    type="button"
                    role="checkbox"
                    aria-checked={checked}
                    onClick={() => toggleSubject(s.id)}
                    className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-right transition-colors hover:bg-muted/60"
                  >
                    <Checkbox
                      checked={checked}
                      tabIndex={-1}
                      className="pointer-events-none"
                    />
                    <span className="min-w-0 flex-1 truncate text-sm">{s.name}</span>
                    <span className="flex shrink-0 items-center gap-1.5">
                      {s.gradeLabel && (
                        <Badge variant="secondary" className="font-normal">
                          {s.gradeLabel}
                        </Badge>
                      )}
                      {!s.isGlobal && (
                        <Badge variant="outline" className="gap-1 font-normal">
                          <Building2 className="h-3 w-3" />
                          {s.organizationName || 'سازمانی'}
                        </Badge>
                      )}
                    </span>
                  </button>
                );
              })}
          </div>
        </ScrollArea>

        {/* sticky footer: live count + save */}
        <div className="flex shrink-0 items-center justify-between gap-3 border-t px-5 py-3">
          <span className="text-sm text-muted-foreground">
            {toPersianDigits(selected.size)} درس انتخاب‌شده
          </span>
          <Button onClick={save} disabled={saving || loading || !!error || !catalog}>
            {saving && <Loader2 className="ml-2 h-4 w-4 animate-spin" />}
            {saving ? 'در حال ذخیره…' : 'ذخیره'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
