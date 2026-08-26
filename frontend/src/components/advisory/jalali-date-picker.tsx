'use client';

/**
 * Canonical Jalali date / date-time pickers for the advisory cards.
 *
 * Built on `react-multi-date-picker` (shahabyazdi) with the built-in
 * `persian` calendar + `fa` locale so every date AND time field speaks
 * Shamsi with Persian digits, per the owner's mandate («برای همه ساعت‌ها و
 * همه تاریخ‌ها میخواهم از ویجت استفاده بشه… حتما هم شمسی»).
 *
 * Wire contract stays Gregorian ISO:
 * - `JalaliDatePicker`     value `YYYY-MM-DD`       → onChange(iso)
 * - `JalaliDateTimePicker` value `YYYY-MM-DDTHH:mm` → onChange(value)
 * Clearing emits `''` (never `null`) so existing form handlers stay
 * unchanged; payload builders already map `'' → null` before hitting the API.
 */

import { useMemo } from 'react';
import { CalendarIcon, X } from 'lucide-react';
import DatePicker from 'react-multi-date-picker';
import TimePicker from 'react-multi-date-picker/plugins/time_picker';
// Calendar/locale objects required by the picker's typings; react-date-object
// is react-multi-date-picker's own bundled dependency (no extra package).
import persian from 'react-date-object/calendars/persian';
import persian_fa from 'react-date-object/locales/persian_fa';

import { formatPersianDate, formatPersianDateTime } from '@/lib/date-utils';
import { cn } from '@/lib/utils';

const ISO_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const ISO_DATETIME_PATTERN = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/;

/** Parse an ISO `YYYY-MM-DD[THH:mm]` into a LOCAL Date (no UTC shift). */
function parseLocalIso(value: string | null | undefined, withTime: boolean): Date | null {
  if (!value) return null;
  const pattern = withTime ? ISO_DATETIME_PATTERN : ISO_DATE_PATTERN;
  const match = pattern.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = withTime ? Number(match[4]) : 0;
  const minute = withTime ? Number(match[5]) : 0;
  const date = new Date(year, month - 1, day, hour, minute, 0, 0);
  return Number.isNaN(date.getTime()) ? null : date;
}

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

function toIsoDate(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

function toIsoDateTime(date: Date): string {
  return `${toIsoDate(date)}T${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

/**
 * Narrow the picker's change argument structurally (DateObject | DateObject[]
 * | null) without importing the library's DateObject type.
 */
function pickerArgToDate(arg: unknown): Date | null {
  if (!arg) return null;
  const first: unknown = Array.isArray(arg) ? arg[0] : arg;
  if (!first || typeof first !== 'object') return null;
  if (first instanceof Date) return Number.isNaN(first.getTime()) ? null : first;
  const candidate = first as { toDate?: () => Date };
  if (typeof candidate.toDate === 'function') {
    const date = candidate.toDate();
    return Number.isNaN(date.getTime()) ? null : date;
  }
  return null;
}

type PickerTriggerProps = {
  id?: string;
  disabled?: boolean;
  hasValue: boolean;
  label: string;
  onOpen: () => void;
  clearable: boolean;
  onClear: () => void;
};

/**
 * Input-styled trigger (h-9 rounded-lg text-sm like ui/input) with the
 * calendar icon at the START edge (visual right under RTL) and an optional
 * clear affordance at the END edge.
 */
function PickerTrigger({
  id,
  disabled = false,
  hasValue,
  label,
  onOpen,
  clearable,
  onClear,
}: PickerTriggerProps) {
  return (
    <div className="relative w-full">
      <button
        id={id}
        type="button"
        onClick={onOpen}
        disabled={disabled}
        aria-haspopup="dialog"
        className={cn(
          'flex h-9 w-full items-center gap-2 rounded-lg border border-input bg-background px-3 py-2 text-sm',
          'ring-offset-background placeholder:text-muted-foreground',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          'disabled:cursor-not-allowed disabled:opacity-50',
          !hasValue && 'text-muted-foreground',
        )}
      >
        <CalendarIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="min-w-0 flex-1 truncate text-right">{label}</span>
      </button>
      {clearable && hasValue && !disabled && (
        <button
          type="button"
          aria-label="پاک کردن تاریخ"
          onClick={onClear}
          className="absolute inset-y-0 end-2 my-auto flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

type JalaliDatePickerProps = {
  /** ISO `YYYY-MM-DD`; `null`/`undefined`/`''` all mean "nothing picked". */
  value?: string | null;
  /** Emits ISO `YYYY-MM-DD`, or `''` when cleared. */
  onChange: (isoDate: string) => void;
  placeholder?: string;
  disabled?: boolean;
  /** Show the ? clear affordance when a date is picked (default true). */
  clearable?: boolean;
  id?: string;
  className?: string;
  /** Optional ISO lower bound — dates before it are unselectable. */
  minDate?: string | null;
  /** Optional ISO upper bound — dates after it are unselectable. */
  maxDate?: string | null;
};

/** Date-only Shamsi picker. The one widget every advisor date field uses. */
export function JalaliDatePicker({
  value,
  onChange,
  placeholder = '?????? ????? ????',
  disabled = false,
  clearable = true,
  id,
  className,
  minDate,
  maxDate,
}: JalaliDatePickerProps) {
  const selected = useMemo(() => parseLocalIso(value, false), [value]);
  const minDateDate = useMemo(() => parseLocalIso(minDate, false), [minDate]);
  const maxDateDate = useMemo(() => parseLocalIso(maxDate, false), [maxDate]);
  const label = selected ? formatPersianDate(selected) : placeholder;

  return (
    <div className={cn('ai-jalali', className)}>
      <DatePicker
        calendar={persian}
        locale={persian_fa}
        format="YYYY/MM/DD"
        value={selected ?? undefined}
        minDate={minDateDate ?? undefined}
        maxDate={maxDateDate ?? undefined}
        onChange={(date) => {
          const picked = pickerArgToDate(date);
          if (picked) onChange(toIsoDate(picked));
        }}
        disabled={disabled}
        arrow={false}
        shadow={false}
        render={(valueText, openCalendar) => (
          <PickerTrigger
            id={id}
            disabled={disabled}
            hasValue={Boolean(selected)}
            label={label}
            onOpen={() => openCalendar()}
            clearable={clearable}
            onClear={() => onChange('')}
          />
        )}
      />
      <JalaliPopoverTheme />
    </div>
  );
}

type JalaliDateTimePickerProps = {
  /** Local `YYYY-MM-DDTHH:mm`; `null`/`undefined`/`''` mean “nothing picked”. */
  value?: string | null;
  /** Emits `YYYY-MM-DDTHH:mm`, or `''` when cleared. */
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  clearable?: boolean;
  id?: string;
  className?: string;
};

/**
 * Date + time Shamsi picker (official TimePicker plugin inside the same
 * popover) for any future time-of-day fields; wire value stays local
 * `YYYY-MM-DDTHH:mm`.
 */
export function JalaliDateTimePicker({
  value,
  onChange,
  placeholder = 'انتخاب تاریخ و ساعت',
  disabled = false,
  clearable = true,
  id,
  className,
}: JalaliDateTimePickerProps) {
  const selected = useMemo(() => parseLocalIso(value, true), [value]);
  const label = selected ? formatPersianDateTime(selected) : placeholder;

  return (
    <div className={cn('ai-jalali', className)}>
      <DatePicker
        calendar={persian}
        locale={persian_fa}
        format="YYYY/MM/DD HH:mm"
        value={selected ?? undefined}
        onChange={(date) => {
          const picked = pickerArgToDate(date);
          if (picked) onChange(toIsoDateTime(picked));
        }}
        disabled={disabled}
        arrow={false}
        shadow={false}
        plugins={[<TimePicker key="time-picker" position="bottom" />]}
        render={(valueText, openCalendar) => (
          <PickerTrigger
            id={id}
            disabled={disabled}
            hasValue={Boolean(selected)}
            label={label}
            onOpen={() => openCalendar()}
            clearable={clearable}
            onClear={() => onChange('')}
          />
        )}
      />
      <JalaliPopoverTheme />
    </div>
  );
}

/**
 * Dark-theme overrides for the library's `.rmdp-*` markup, scoped to the
 * `.ai-jalali` wrapper so nothing else on the page is touched. Maps the
 * calendar onto the app's HSL tokens (bg-popover / border-border / primary).
 */
function JalaliPopoverTheme() {
  return (
    <style jsx global>{`
      .ai-jalali {
        direction: rtl;
      }
      .ai-jalali .rmdp-container {
        width: 100%;
      }
      /* ── popup panel ─────────────────────────────────────────────── */
      .ai-jalali .rmdp-wrapper {
        direction: rtl;
        z-index: 50;
        background: hsl(var(--popover));
        color: hsl(var(--popover-foreground));
        border: 1px solid hsl(var(--border));
        border-radius: 0.75rem;
        box-shadow: 0 16px 40px -12px rgb(0 0 0 / 0.45);
        overflow: hidden;
        font-family: inherit;
      }
      .ai-jalali .rmdp-shadow {
        box-shadow: none;
      }
      .ai-jalali .rmdp-calendar {
        padding: 0.5rem;
      }
      /* ── header + navigation arrows ──────────────────────────────── */
      .ai-jalali .rmdp-header-values {
        color: hsl(var(--foreground));
        font-weight: 600;
        font-size: 0.875rem;
      }
      .ai-jalali .rmdp-arrow-container {
        border-radius: 9999px;
        background: transparent;
        box-shadow: none;
      }
      .ai-jalali .rmdp-arrow-container:hover {
        background: hsl(var(--muted));
        box-shadow: none;
      }
      .ai-jalali .rmdp-arrow {
        border-color: hsl(var(--muted-foreground));
      }
      .ai-jalali .rmdp-arrow-container:hover .rmdp-arrow {
        border-color: hsl(var(--foreground));
      }
      /* ── weekday header ──────────────────────────────────────────── */
      .ai-jalali .rmdp-week-day {
        color: hsl(var(--muted-foreground));
        font-size: 0.7rem;
      }
      /* ── days ────────────────────────────────────────────────────── */
      .ai-jalali .rmdp-day {
        color: hsl(var(--foreground));
      }
      .ai-jalali .rmdp-day span {
        border-radius: 0.5rem;
        font-size: 0.75rem;
      }
      .ai-jalali .rmdp-day:not(.rmdp-disabled):not(.rmdp-deactive) span:hover {
        background: hsl(var(--muted));
        color: hsl(var(--foreground));
        box-shadow: none;
      }
      .ai-jalali .rmdp-day.rmdp-today span {
        background: transparent;
        color: hsl(var(--primary));
        border: 1px solid hsl(var(--primary) / 0.6);
      }
      .ai-jalali .rmdp-day.rmdp-selected span:not(.highlight) {
        background: hsl(var(--primary));
        color: hsl(var(--primary-foreground));
        box-shadow: none;
      }
      .ai-jalali .rmdp-day.rmdp-deactive,
      .ai-jalali .rmdp-day.rmdp-day-hidden {
        color: hsl(var(--muted-foreground) / 0.45);
      }
      .ai-jalali .rmdp-day.rmdp-disabled,
      .ai-jalali .rmdp-day.rmdp-disabled span {
        opacity: 0.35;
        cursor: not-allowed;
      }
      /* ── month / year overlay sheets ─────────────────────────────── */
      .ai-jalali .rmdp-month-picker,
      .ai-jalali .rmdp-year-picker {
        background: hsl(var(--popover));
        border: 1px solid hsl(var(--border));
        border-radius: 0.5rem;
        box-shadow: 0 12px 32px -12px rgb(0 0 0 / 0.4);
      }
      .ai-jalali .rmdp-month-picker span,
      .ai-jalali .rmdp-year-picker span {
        color: hsl(var(--foreground));
        border-radius: 0.375rem;
      }
      .ai-jalali .rmdp-month-picker span:hover,
      .ai-jalali .rmdp-year-picker span:hover {
        background: hsl(var(--muted));
        color: hsl(var(--foreground));
      }
      /* ── TimePicker plugin strip ─────────────────────────────────── */
      .ai-jalali .rmdp-time-picker {
        direction: ltr;
        color: hsl(var(--foreground));
        margin-top: 0.25rem;
        padding-top: 0.25rem;
        border-top: 1px solid hsl(var(--border));
      }
      .ai-jalali .rmdp-time-picker input,
      .ai-jalali .rmdp-time-picker select {
        background: hsl(var(--background));
        color: hsl(var(--foreground));
        border: 1px solid hsl(var(--border));
        border-radius: 0.375rem;
      }
    `}</style>
  );
}
