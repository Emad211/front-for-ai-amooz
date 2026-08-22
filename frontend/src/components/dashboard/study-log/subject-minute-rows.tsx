'use client';

import { Plus } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { StudyLogItem, StudentSubjectRow } from '@/services/advisory-service';
import { toPersianDigits } from '@/lib/persian-digits';

const QUICK_ADD_MINUTES = [15, 30, 60] as const;

type SubjectMinuteRowsProps = {
  subjects: StudentSubjectRow[];
  /** Raw (sanitized ASCII-digit) input string per subjectId. */
  minutesBySubject: Record<number, string>;
  /** Log items whose subject left the advisor's list — read-only history. */
  removedItems: StudyLogItem[];
  onMinutesChange: (subjectId: number, raw: string) => void;
  onQuickAdd: (subjectId: number, delta: number) => void;
  disabled?: boolean;
};

export function SubjectMinuteRows({
  subjects,
  minutesBySubject,
  removedItems,
  onMinutesChange,
  onQuickAdd,
  disabled,
}: SubjectMinuteRowsProps) {
  if (subjects.length === 0 && removedItems.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-border py-8 text-center text-sm text-muted-foreground">
        هنوز درسی برای شما انتخاب نشده است.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        {subjects.map((subject) => {
          const raw = minutesBySubject[subject.subjectId] ?? '';
          return (
            <div
              key={subject.subjectId}
              className="flex flex-wrap items-center gap-2 rounded-md border border-border p-3"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{subject.name}</p>
                {subject.gradeLabel ? (
                  <p className="text-xs text-muted-foreground">{subject.gradeLabel}</p>
                ) : null}
              </div>

              <div className="flex items-center gap-1">
                {QUICK_ADD_MINUTES.map((delta) => (
                  <Button
                    key={delta}
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={disabled}
                    onClick={() => onQuickAdd(subject.subjectId, delta)}
                    aria-label={`افزودن ${toPersianDigits(delta)} دقیقه به ${subject.name}`}
                    className="h-7 rounded-full px-2 text-xs"
                  >
                    <Plus className="me-0.5 h-3 w-3" />
                    {toPersianDigits(delta)}
                  </Button>
                ))}
              </div>

              <div className="flex items-center gap-1.5">
                <Input
                  type="text"
                  inputMode="numeric"
                  dir="ltr"
                  value={toPersianDigits(raw)}
                  onChange={(e) => onMinutesChange(subject.subjectId, e.target.value)}
                  disabled={disabled}
                  aria-label={`دقایق مطالعهٔ ${subject.name}`}
                  className="h-9 w-20 text-center"
                />
                <span className="text-xs text-muted-foreground">دقیقه</span>
              </div>
            </div>
          );
        })}
      </div>

      {removedItems.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">درس‌های حذف‌شده از فهرست:</p>
          {removedItems.map((item) => (
            <div
              key={item.subjectId}
              className="flex items-center justify-between gap-2 rounded-md border border-border/60 bg-muted/40 p-3 opacity-80"
            >
              <div className="flex min-w-0 items-center gap-2">
                <Badge variant="outline">حذف‌شده از فهرست</Badge>
                <span className="truncate text-sm">{item.name}</span>
              </div>
              <div className="flex shrink-0 items-center gap-1.5">
                <Input
                  dir="ltr"
                  value={toPersianDigits(item.minutes)}
                  disabled
                  readOnly
                  aria-label={`دقایق ثبت‌شدهٔ ${item.name}`}
                  className="h-9 w-20 bg-transparent text-center"
                />
                <span className="text-xs text-muted-foreground">دقیقه</span>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
