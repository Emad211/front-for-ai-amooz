'use client';

import { useEffect, useMemo, useState } from 'react';
import { CalendarIcon, ChevronLeft, ChevronRight, Clock3, X } from 'lucide-react';
import { DayPicker } from 'react-day-picker/persian';

import { Button, buttonVariants } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { formatPersianDateTime } from '@/lib/date-utils';
import { toPersianDigits } from '@/lib/persian-digits';
import { cn } from '@/lib/utils';

type JalaliDateTimePickerProps = {
  className?: string;
  disabled?: boolean;
  id?: string;
  onChange: (value: string) => void;
  placeholder?: string;
  value: string;
};

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, '0'));
const MINUTE_OPTIONS = Array.from({ length: 60 }, (_, index) => String(index).padStart(2, '0'));

function formatLocalDateTimeValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hour = String(date.getHours()).padStart(2, '0');
  const minute = String(date.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hour}:${minute}`;
}

function parseLocalDateTimeValue(value: string): Date | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
}

function applyTime(date: Date, hour: string, minute: string): Date {
  const next = new Date(date);
  next.setHours(Number(hour), Number(minute), 0, 0);
  return next;
}

export function JalaliDateTimePicker({
  className,
  disabled = false,
  id,
  onChange,
  placeholder = 'تاریخ و ساعت را انتخاب کنید',
  value,
}: JalaliDateTimePickerProps) {
  const selected = useMemo(() => parseLocalDateTimeValue(value), [value]);
  const [open, setOpen] = useState(false);
  const [hour, setHour] = useState('23');
  const [minute, setMinute] = useState('59');

  useEffect(() => {
    if (!selected) return;
    setHour(String(selected.getHours()).padStart(2, '0'));
    setMinute(String(selected.getMinutes()).padStart(2, '0'));
  }, [selected]);

  const commitDate = (date: Date) => {
    onChange(formatLocalDateTimeValue(applyTime(date, hour, minute)));
  };

  const handleSelect = (date: Date | undefined) => {
    if (!date) return;
    commitDate(date);
  };

  const handleTimeChange = (nextHour: string, nextMinute: string) => {
    setHour(nextHour);
    setMinute(nextMinute);

    if (!selected) return;
    onChange(formatLocalDateTimeValue(applyTime(selected, nextHour, nextMinute)));
  };

  const triggerLabel = selected ? formatPersianDateTime(selected) : placeholder;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          disabled={disabled}
          className={cn(
            'h-11 w-full justify-between rounded-lg border-border bg-background px-3 text-right font-normal hover:bg-background',
            !selected && 'text-muted-foreground',
            className,
          )}
        >
          <span className="truncate">{triggerLabel}</span>
          <CalendarIcon className="h-4 w-4 shrink-0" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        side="bottom"
        align="end"
        sideOffset={10}
        collisionPadding={12}
        className="w-[min(24rem,calc(100vw-1rem))] overflow-visible rounded-2xl border-border bg-card p-0 shadow-2xl"
        dir="rtl"
      >
        <div className="space-y-4 p-4">
          <div className="space-y-1 px-1">
            <p className="text-sm font-semibold text-foreground">انتخاب مهلت شمسی</p>
            <p className="text-xs text-muted-foreground">
              تاریخ را از تقویم انتخاب کنید و ساعت را دقیق تنظیم کنید.
            </p>
          </div>

          <div className="overflow-hidden rounded-2xl border border-border/80 bg-background/70 p-3">
            <DayPicker
              mode="single"
              selected={selected ?? undefined}
              onSelect={handleSelect}
              dir="rtl"
              numerals="arabext"
              showOutsideDays
              fixedWeeks
              className="p-0"
              classNames={{
                root: 'w-full',
                months: 'flex w-full flex-col',
                month: 'w-full space-y-3',
                caption: 'relative flex min-h-10 items-center justify-center px-12 py-1',
                caption_label: 'text-base font-semibold text-foreground',
                nav: 'flex items-center gap-1',
                button_previous:
                  'absolute right-1 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full border border-border bg-card text-muted-foreground transition hover:bg-muted hover:text-foreground',
                button_next:
                  'absolute left-1 top-1/2 inline-flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full border border-border bg-card text-muted-foreground transition hover:bg-muted hover:text-foreground',
                month_caption: 'flex justify-center',
                month_grid: 'w-full table-fixed border-separate border-spacing-1',
                weekdays: 'grid w-full grid-cols-7 gap-1',
                weekday:
                  'flex h-10 items-center justify-center rounded-lg text-base font-medium tabular-nums text-muted-foreground',
                weeks: 'grid w-full gap-1',
                week: 'grid w-full grid-cols-7 gap-1',
                day: cn(
                  buttonVariants({ variant: 'ghost' }),
                  'h-11 w-full min-w-0 rounded-xl p-0 text-base font-semibold tabular-nums leading-none text-foreground hover:bg-muted aria-selected:opacity-100',
                ),
                day_button: 'h-11 w-full text-center tabular-nums',
                selected:
                  'bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground',
                today: 'border border-primary/50 bg-primary/10 text-primary',
                outside: 'text-muted-foreground/40',
                disabled: 'opacity-40',
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

          <div className="space-y-2 rounded-2xl border border-border/80 bg-background/70 p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Clock3 className="h-4 w-4 text-primary" />
              <span>ساعت مهلت</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <span className="text-xs text-muted-foreground">ساعت</span>
                <Select
                  value={hour}
                  onValueChange={(nextHour) => handleTimeChange(nextHour, minute)}
                  disabled={disabled}
                >
                  <SelectTrigger className="bg-background">
                    <SelectValue placeholder="ساعت" />
                  </SelectTrigger>
                  <SelectContent>
                    {HOUR_OPTIONS.map((option) => (
                      <SelectItem key={option} value={option}>
                        {toPersianDigits(option)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <span className="text-xs text-muted-foreground">دقیقه</span>
                <Select
                  value={minute}
                  onValueChange={(nextMinute) => handleTimeChange(hour, nextMinute)}
                  disabled={disabled}
                >
                  <SelectTrigger className="bg-background">
                    <SelectValue placeholder="دقیقه" />
                  </SelectTrigger>
                  <SelectContent>
                    {MINUTE_OPTIONS.map((option) => (
                      <SelectItem key={option} value={option}>
                        {toPersianDigits(option)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-3 border-t border-border px-1 pt-1 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="ghost"
                className="px-2 text-muted-foreground hover:text-foreground"
                onClick={() => {
                  const now = new Date();
                  onChange(formatLocalDateTimeValue(applyTime(now, hour, minute)));
                }}
              >
                امروز
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="px-2 text-muted-foreground hover:text-foreground"
                onClick={() => setOpen(false)}
              >
                بستن
              </Button>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2">
              {selected ? (
                <span className="text-xs text-muted-foreground">{formatPersianDateTime(selected)}</span>
              ) : (
                <span className="text-xs text-muted-foreground">هنوز زمانی انتخاب نشده است.</span>
              )}
              {selected ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground hover:text-destructive"
                  onClick={() => onChange('')}
                    aria-label="پاک کردن مهلت"
                >
                  <X className="h-4 w-4" />
                </Button>
              ) : null}
              <Button
                type="button"
                size="sm"
                onClick={() => setOpen(false)}
                disabled={!selected}
              >
                تایید
              </Button>
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
