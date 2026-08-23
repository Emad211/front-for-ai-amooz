'use client';

import { useState } from 'react';
import { CalendarIcon, ChevronLeft, ChevronRight } from 'lucide-react';
import { DayPicker } from 'react-day-picker/persian';

import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { formatPersianDate } from '@/lib/date-utils';
import { cn } from '@/lib/utils';

/**
 * Date-only Jalali picker for a study plan's start date.
 *
 * `jalali-date-time-picker.tsx` could not be reused here: it hard-codes a
 * future-only rule and always carries a time-of-day, while a plan may legally
 * start on any day ≥ the engagement's start (often in the past) and is
 * date-granular on the wire (`YYYY-MM-DD`). Same DayPicker persian recipe,
 * minus time and future gating; an optional inclusive lower bound replaces it.
 */
type JalaliDatePickerProps = {
  /** ISO `YYYY-MM-DD`, or '' when nothing is picked yet. */
  value: string;
  onChange: (isoDate: string) => void;
  disabled?: boolean;
  placeholder?: string;
  id?: string;
  /** Inclusive lower bound as ISO `YYYY-MM-DD` (e.g. the engagement start). */
  minDate?: string | null;
};

function parseIsoDate(iso: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(date.getTime()) ? null : date;
}

function toIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function JalaliDatePicker({
  value,
  onChange,
  disabled = false,
  placeholder = 'تاریخ شروع را انتخاب کنید',
  id,
  minDate,
}: JalaliDatePickerProps) {
  const [open, setOpen] = useState(false);
  const selected = parseIsoDate(value);
  const minDay = parseIsoDate(minDate ?? '');

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          disabled={disabled}
          className={cn(
            'h-10 w-full justify-between rounded-lg border-border bg-background px-3 text-right font-normal hover:bg-background',
            !selected && 'text-muted-foreground',
          )}
        >
          <span className="truncate">{selected ? formatPersianDate(value) : placeholder}</span>
          <CalendarIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        side="bottom"
        align="end"
        sideOffset={10}
        collisionPadding={12}
        className="w-[min(20rem,calc(100vw-1rem))] overflow-visible rounded-2xl border-border bg-card p-0 shadow-2xl"
        dir="rtl"
      >
        <div className="space-y-3 p-4">
          <p className="px-1 text-sm font-semibold text-foreground">انتخاب تاریخ شمسی</p>
          <div className="overflow-hidden rounded-2xl border border-border/80 bg-card p-3 text-card-foreground">
            <DayPicker
              mode="single"
              selected={selected ?? undefined}
              onSelect={(date) => {
                if (!date) return;
                onChange(toIsoDate(date));
                setOpen(false);
              }}
              disabled={minDay ? { before: minDay } : undefined}
              dir="rtl"
              numerals="arabext"
              showOutsideDays
              fixedWeeks
              className="p-0"
              classNames={{
                root: 'w-full',
                months: 'flex w-full flex-col',
                month: 'relative w-full space-y-3',
                caption_label: 'text-base font-semibold text-foreground',
                nav: 'absolute inset-x-0 top-0 z-10 flex h-10 items-center justify-between px-1',
                button_previous:
                  'inline-flex h-8 w-8 items-center justify-center rounded-full border border-border bg-card text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
                button_next:
                  'inline-flex h-8 w-8 items-center justify-center rounded-full border border-border bg-card text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
                month_caption: 'flex h-10 items-center justify-center px-12',
                month_grid: 'w-full table-fixed border-separate border-spacing-1 bg-card',
                weekdays: 'table-row',
                weekday:
                  'h-9 w-[14.285%] p-0 text-center text-sm font-medium tabular-nums text-muted-foreground',
                weeks: 'table-row-group',
                week: 'table-row',
                day: 'h-10 w-[14.285%] p-0 text-center align-middle',
                day_button:
                  'inline-flex h-9 w-full min-w-0 items-center justify-center rounded-xl bg-card p-0 text-sm font-semibold leading-none tabular-nums text-card-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-card',
                selected:
                  '[&>button]:bg-primary [&>button]:text-primary-foreground [&>button]:hover:bg-primary/90',
                today:
                  '[&>button]:border [&>button]:border-primary/60 [&>button]:bg-primary/10 [&>button]:text-primary',
                outside: '[&>button]:text-muted-foreground/40',
                disabled: '[&>button]:cursor-not-allowed [&>button]:opacity-35',
              }}
              components={{
                Chevron: ({ className, orientation }) =>
                  orientation === 'left' ? (
                    <ChevronLeft className={cn('h-4 w-4', className)} />
                  ) : (
                    <ChevronRight className={cn('h-4 w-4', className)} />
                  ),
              }}
            />
          </div>
          {minDay && (
            <p className="px-1 text-xs text-muted-foreground">
              تاریخ‌های پیش از {formatPersianDate(minDate ?? '')} در دسترس نیستند.
            </p>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
