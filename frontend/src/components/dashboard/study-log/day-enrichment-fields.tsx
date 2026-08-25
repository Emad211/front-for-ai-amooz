'use client';

/**
 * Day enrichment fields (restart step 1) — هدف روز، جمله انگیزشی، تعداد تست،
 * درصد آزمون. Presentational: the page owns the string state and sanitizes on
 * change, so an out-of-range value can never reach the submit handler.
 */
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { toPersianDigits } from '@/lib/persian-digits';

const TEXT_MAX_LENGTH = 200;

type DayEnrichmentFieldsProps = {
  dayGoal: string;
  motivationNote: string;
  testsTaken: string;
  testPercent: string;
  onDayGoalChange: (value: string) => void;
  onMotivationNoteChange: (value: string) => void;
  onTestsTakenChange: (value: string) => void;
  onTestPercentChange: (value: string) => void;
  disabled?: boolean;
};

function CharCounter({ value }: { value: string }) {
  return (
    <span className="text-xs text-muted-foreground">
      {toPersianDigits(value.length)} / {toPersianDigits(TEXT_MAX_LENGTH)}
    </span>
  );
}

export function DayEnrichmentFields({
  dayGoal,
  motivationNote,
  testsTaken,
  testPercent,
  onDayGoalChange,
  onMotivationNoteChange,
  onTestsTakenChange,
  onTestPercentChange,
  disabled,
}: DayEnrichmentFieldsProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="space-y-2 sm:col-span-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="day-goal">هدف روز</Label>
          <CharCounter value={dayGoal} />
        </div>
        <Textarea
          id="day-goal"
          value={dayGoal}
          onChange={(e) => onDayGoalChange(e.target.value.slice(0, TEXT_MAX_LENGTH))}
          maxLength={TEXT_MAX_LENGTH}
          rows={2}
          disabled={disabled}
          placeholder="امروز می‌خواهی به چه هدفی برسی؟"
        />
      </div>

      <div className="space-y-2 sm:col-span-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="motivation-note">جمله انگیزشی</Label>
          <CharCounter value={motivationNote} />
        </div>
        <Input
          id="motivation-note"
          value={motivationNote}
          onChange={(e) => onMotivationNoteChange(e.target.value.slice(0, TEXT_MAX_LENGTH))}
          maxLength={TEXT_MAX_LENGTH}
          disabled={disabled}
          placeholder="یک جمله که امروز تو را جلو می‌برد…"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="tests-taken">تعداد تست</Label>
        <Input
          id="tests-taken"
          inputMode="numeric"
          value={testsTaken}
          onChange={(e) => onTestsTakenChange(e.target.value)}
          disabled={disabled}
          placeholder="۰"
          aria-label="تعداد تست"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="test-percent">درصد آزمون</Label>
        <Input
          id="test-percent"
          inputMode="numeric"
          value={testPercent}
          onChange={(e) => onTestPercentChange(e.target.value)}
          disabled={disabled}
          placeholder="خالی = ثبت نشده"
          aria-label="درصد آزمون"
        />
        <p className="text-xs text-muted-foreground">عددی بین ۰ تا ۱۰۰</p>
      </div>
    </div>
  );
}
