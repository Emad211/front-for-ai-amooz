'use client';

import { ChevronLeft, ChevronRight } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { formatPersianDate } from '@/lib/date-utils';

type StudyLogHeaderProps = {
  /** ISO `YYYY-MM-DD` currently being edited. */
  date: string;
  minDate: string | null;
  maxDate: string | null;
  onPrevDay: () => void;
  onNextDay: () => void;
};

export function StudyLogHeader({
  date,
  minDate,
  maxDate,
  onPrevDay,
  onNextDay,
}: StudyLogHeaderProps) {
  // ISO strings compare lexicographically — that IS chronological order.
  const canGoPrev = minDate === null || date > minDate;
  const canGoNext = maxDate === null || date < maxDate;

  return (
    <div className="flex flex-wrap items-center justify-end gap-3">
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={onPrevDay}
          disabled={!canGoPrev}
          aria-label="روز قبل"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
        <span className="min-w-28 text-center text-sm font-semibold md:text-base">
          {formatPersianDate(`${date}T00:00:00`)}
        </span>
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={onNextDay}
          disabled={!canGoNext}
          aria-label="روز بعد"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
