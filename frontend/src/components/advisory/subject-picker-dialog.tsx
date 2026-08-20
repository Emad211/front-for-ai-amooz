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
 * can have moved since last time, and the student's grade seeds the grade filter.
 *
 * The grade chips are a *convenience filter only*. An untagged subject ("all
 * levels") is always shown, and a 12th-grader who studies grades 10–12 (the konkur
 * reality) can widen the filter to several grades at once — so the filter never
 * hides a subject the advisor legitimately wants to assign. Assignability itself is
 * decided server-side; this dialog only helps the advisor find the row.
 */
const GRADE_CHIPS: { code: string; label: string }[] = [
  { code: '10', label: 'دهم' },
  { code: '11', label: 'یازدهم' },
  { code: '12', label: 'دوازدهم' },
];

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
  // Grade filter: an empty set means «همه» (show every grade). A non-empty set
  // shows only those grades — plus every untagged subject, always.
  const [gradeFilter, setGradeFilter] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);

  // Load the assignable catalog and this student's current selection together,
  // each time the dialog opens. The student's grade pre-selects its own chip.
  useEffect(() => {
    if (!open) return;
    let active = true;
    setError('');
    setCatalog(null);
    setQuery('');

    Promise.all([
      AdvisoryService.getSubjects(),
      AdvisoryService.getEngagementSubjects(engagementId),
    ])
      .then(([subjects, current]) => {
        if (!active) return;
        setCatalog(subjects);
        setSelected(new Set(current.selectedSubjectIds));
        setGradeFilter(
          current.studentGrade ? new Set([current.studentGrade]) : new Set(),
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
    return catalog.filter((s) => {
      if (!matchesSearch(s.name, query)) return false;
      if (gradeFilter.size === 0) return true; // «همه»
      if (s.grade === null) return true; // untagged = all levels
      return gradeFilter.has(s.grade);
    });
  }, [catalog, query, gradeFilter]);

  const toggleSubject = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const toggleGrade = (code: string) =>
    setGradeFilter((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
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
          <DialogTitle className="flex items-center gap-2 text-base">
            <BookOpen className="h-4 w-4 text-primary" />
            درس‌های «{studentName}»
          </DialogTitle>
          <DialogDescription className="text-xs leading-relaxed">
            درس‌ها را انتخاب کنید و «ذخیره» بزنید. هرچه انتخاب نشود کنار گذاشته
            می‌شود. فیلترِ پایه فقط برای پیدا کردنِ سریع‌تر است و چیزی را محدود
            نمی‌کند.
          </DialogDescription>
        </DialogHeader>

        {/* search + grade chips — fixed above the scrolling list */}
        <div className="shrink-0 space-y-2.5 px-5 pt-3">
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
          <div className="flex flex-wrap gap-1.5">
            <Button
              type="button"
              size="sm"
              variant={gradeFilter.size === 0 ? 'default' : 'outline'}
              onClick={() => setGradeFilter(new Set())}
              className="h-7 rounded-full px-3 text-xs"
            >
              همه
            </Button>
            {GRADE_CHIPS.map((g) => (
              <Button
                key={g.code}
                type="button"
                size="sm"
                variant={gradeFilter.has(g.code) ? 'default' : 'outline'}
                onClick={() => toggleGrade(g.code)}
                className="h-7 rounded-full px-3 text-xs"
              >
                {g.label}
              </Button>
            ))}
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
              <p className="px-2 py-8 text-center text-sm text-muted-foreground">
                درسی با این جستجو پیدا نشد.
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
