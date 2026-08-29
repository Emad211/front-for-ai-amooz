'use client';

import { Button } from '@/components/ui/button';
import { toPersianDigits } from '@/lib/persian-digits';

/** Ascending 1→5: بد / نه چندان / متوسط / خوب / عالی. */
const MOOD_LEVELS: { value: number; label: string }[] = [
  { value: 1, label: 'بد' },
  { value: 2, label: 'نه چندان' },
  { value: 3, label: 'متوسط' },
  { value: 4, label: 'خوب' },
  { value: 5, label: 'عالی' },
];

type MoodSelectorProps = {
  /** `null` = not recorded today (the «ثبت نکردم» state). */
  value: number | null;
  onChange: (mood: number | null) => void;
  disabled?: boolean;
};

export function MoodSelector({ value, onChange, disabled }: MoodSelectorProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {MOOD_LEVELS.map((level) => {
        const selected = value === level.value;
        return (
          <Button
            key={level.value}
            type="button"
            variant={selected ? 'default' : 'outline'}
            size="sm"
            disabled={disabled}
            onClick={() => onChange(level.value)}
            aria-pressed={selected}
            className="rounded-full"
          >
            <span className="me-1 text-xs opacity-80">
              {toPersianDigits(level.value)}
            </span>
            {level.label}
          </Button>
        );
      })}
      <Button
        type="button"
        variant={value === null ? 'secondary' : 'ghost'}
        size="sm"
        disabled={disabled}
        onClick={() => onChange(null)}
        aria-pressed={value === null}
      >
        ثبت نکردم
      </Button>
    </div>
  );
}
