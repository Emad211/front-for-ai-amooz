import { newDate, getDaysInMonth, getDay, getYear, getMonth, getDate } from 'date-fns-jalali';

import type { CalendarDay, CalendarEvent } from '@/types';

/**
 * Real Jalali (Solar Hijri) calendar engine, backed by `date-fns-jalali`.
 *
 * Replaces the previous mock engine which hardcoded the first weekday, a frozen
 * "today", and approximate month lengths (it ignored leap years). All month
 * lengths, the first-day weekday, and "today" are now computed from the actual
 * calendar.
 *
 * Conventions:
 * - `month` in the public API is **1-based** (1 = فروردین … 12 = اسفند), matching
 *   the rest of the app. `date-fns-jalali` uses 0-based month indices internally.
 * - The grid column order is the Persian week: شنبه (Saturday) = 0 … جمعه
 *   (Friday) = 6. Friday (column 6) is the weekend.
 * - Event `date` strings are Jalali `YYYY-MM-DD` (zero-padded), so lexical
 *   comparison is chronological.
 */

const pad2 = (n: number): string => String(n).padStart(2, '0');

/** Persian week column for a JS Date: شنبه=0 … جمعه=6 (JS getDay: Sun=0…Sat=6). */
function persianColumn(date: Date): number {
  return (getDay(date) + 1) % 7;
}

/** Today in the Jalali calendar (month is 1-based). */
export function getTodayJalali(): { year: number; month: number; day: number } {
  const now = new Date();
  return { year: getYear(now), month: getMonth(now) + 1, day: getDate(now) };
}

/** Today as a Jalali `YYYY-MM-DD` string (matches event.date format). */
export function getTodayJalaliString(): string {
  const t = getTodayJalali();
  return `${t.year}-${pad2(t.month)}-${pad2(t.day)}`;
}

export function getEventsForDate(date: string, events: CalendarEvent[] = []): CalendarEvent[] {
  return events.filter((event) => event.date === date);
}

/**
 * Build a 42-cell (6×7) month grid for the given Jalali year/month (1-based),
 * padded with the trailing/leading days of the adjacent months.
 */
export function generateMonthDays(year: number, month: number, events: CalendarEvent[] = []): CalendarDay[] {
  const monthIndex = month - 1; // date-fns-jalali is 0-based
  const firstOfMonth = newDate(year, monthIndex, 1);
  const daysInMonth = getDaysInMonth(firstOfMonth);
  const firstColumn = persianColumn(firstOfMonth);
  const today = getTodayJalali();

  const days: CalendarDay[] = [];
  const pushCell = (cell: Omit<CalendarDay, 'isWeekend'>) => {
    days.push({ ...cell, isWeekend: days.length % 7 === 6 });
  };

  // Trailing days of the previous month to fill the first week.
  const prevYear = monthIndex === 0 ? year - 1 : year;
  const prevMonthIndex = monthIndex === 0 ? 11 : monthIndex - 1;
  const prevDaysInMonth = getDaysInMonth(newDate(prevYear, prevMonthIndex, 1));
  for (let i = 0; i < firstColumn; i++) {
    pushCell({
      day: prevDaysInMonth - firstColumn + i + 1,
      isCurrentMonth: false,
      isToday: false,
      events: [],
    });
  }

  // Days of the current month.
  for (let day = 1; day <= daysInMonth; day++) {
    const dateStr = `${year}-${pad2(month)}-${pad2(day)}`;
    pushCell({
      day,
      isCurrentMonth: true,
      isToday: year === today.year && month === today.month && day === today.day,
      events: getEventsForDate(dateStr, events),
    });
  }

  // Leading days of the next month to complete the 6-row grid.
  let nextDay = 1;
  while (days.length < 42) {
    pushCell({
      day: nextDay++,
      isCurrentMonth: false,
      isToday: false,
      events: [],
    });
  }

  return days;
}

export function getUpcomingEvents(
  events: CalendarEvent[],
  limit: number = 5,
  today: string = getTodayJalaliString(),
): CalendarEvent[] {
  return events
    .filter((event) => event.date >= today)
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, limit);
}
