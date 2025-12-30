import type { CalendarDay, CalendarEvent } from '@/types';

export function getEventsForDate(date: string, events: CalendarEvent[] = []): CalendarEvent[] {
  return events.filter((event) => event.date === date);
}

export function generateMonthDays(year: number, month: number, events: CalendarEvent[] = []): CalendarDay[] {
  const daysInMonth = month <= 6 ? 31 : month <= 11 ? 30 : 29;
  const days: CalendarDay[] = [];

  // Get the first day of the month (0 = Saturday in Persian calendar)
  // For mock, let's say دی ۱۴۰۴ starts on یکشنبه (index 1)
  const firstDayIndex = 1;

  // Add empty days from previous month
  for (let i = 0; i < firstDayIndex; i++) {
    const prevMonthDays = month === 1 ? 29 : month <= 7 ? 31 : 30;
    days.push({
      day: prevMonthDays - firstDayIndex + i + 1,
      isCurrentMonth: false,
      isToday: false,
      isWeekend: i === 6,
      events: [],
    });
  }

  // Add days of current month
  for (let day = 1; day <= daysInMonth; day++) {
    const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const dayIndex = (firstDayIndex + day - 1) % 7;

    days.push({
      day,
      isCurrentMonth: true,
      isToday: day === 7,
      isWeekend: dayIndex === 6,
      events: getEventsForDate(dateStr, events),
    });
  }

  // Add days from next month to complete the grid
  const remainingDays = 42 - days.length;
  for (let i = 1; i <= remainingDays; i++) {
    days.push({
      day: i,
      isCurrentMonth: false,
      isToday: false,
      isWeekend: (days.length + i - 1) % 7 === 6,
      events: [],
    });
  }

  return days;
}

export function getUpcomingEvents(
  events: CalendarEvent[],
  limit: number = 5,
  today: string = '1404-10-07'
): CalendarEvent[] {
  return events
    .filter((event) => event.date >= today)
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, limit);
}
