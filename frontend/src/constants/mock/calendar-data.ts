/**
 * =============================================================================
 * CALENDAR MOCK DATA - داده‌های آزمایشی تقویم
 * =============================================================================
 * 
 * برای اتصال به Backend:
 * این داده‌ها را با API call به endpoint زیر جایگزین کنید:
 * GET /api/calendar/events
 * GET /api/calendar/events?month=:month&year=:year
 * POST /api/calendar/events
 * PUT /api/calendar/events/:id
 * DELETE /api/calendar/events/:id
 * 
 * =============================================================================
 */

import { CalendarEvent, CalendarDay, EventType, EventPriority } from "@/types";

export const EVENT_TYPE_CONFIG: Record<EventType, { label: string; color: string; bgColor: string }> = {
  exam: { 
    label: 'آزمون', 
    color: 'text-red-500', 
    bgColor: 'bg-red-500/10' 
  },
  assignment: { 
    label: 'تکلیف', 
    color: 'text-orange-500', 
    bgColor: 'bg-orange-500/10' 
  },
  class: { 
    label: 'کلاس', 
    color: 'text-blue-500', 
    bgColor: 'bg-blue-500/10' 
  },
  holiday: { 
    label: 'تعطیلی', 
    color: 'text-green-500', 
    bgColor: 'bg-green-500/10' 
  },
  reminder: { 
    label: 'یادآوری', 
    color: 'text-purple-500', 
    bgColor: 'bg-purple-500/10' 
  },
};

export const PERSIAN_MONTHS = [
  'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
  'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'
];

export const PERSIAN_WEEKDAYS = [
  'شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه'
];

export const PERSIAN_WEEKDAYS_SHORT = [
  'ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج'
];

// Mock Events Data - دی ماه ۱۴۰۴
export const MOCK_CALENDAR_EVENTS: CalendarEvent[] = [
  {
    id: '1',
    title: 'آزمون میان‌ترم ریاضی',
    description: 'آزمون از فصل ۱ تا ۴',
    date: '1404-10-15',
    time: '10:00',
    endTime: '12:00',
    type: 'exam',
    priority: 'high',
    subject: 'ریاضی',
    location: 'آنلاین',
  },
  {
    id: '2',
    title: 'تحویل پروژه فیزیک',
    description: 'پروژه آزمایشگاه فیزیک ۲',
    date: '1404-10-20',
    type: 'assignment',
    priority: 'high',
    subject: 'فیزیک',
  },
  {
    id: '3',
    title: 'کلاس آنلاین شیمی',
    description: 'جلسه رفع اشکال',
    date: '1404-10-08',
    time: '16:00',
    endTime: '17:30',
    type: 'class',
    priority: 'medium',
    subject: 'شیمی',
    location: 'آنلاین',
  },
  {
    id: '4',
    title: 'کلاس زیست‌شناسی',
    description: 'فصل ۵ - ژنتیک',
    date: '1404-10-10',
    time: '14:00',
    endTime: '15:30',
    type: 'class',
    priority: 'medium',
    subject: 'زیست‌شناسی',
  },
  {
    id: '5',
    title: 'تعطیلات زمستانی',
    date: '1404-10-22',
    type: 'holiday',
    priority: 'low',
  },
  {
    id: '6',
    title: 'یادآوری: ثبت‌نام کلاس',
    description: 'ثبت‌نام کلاس‌های ترم جدید',
    date: '1404-10-05',
    type: 'reminder',
    priority: 'medium',
  },
  {
    id: '7',
    title: 'آزمون آزمایشی کنکور',
    description: 'آزمون جامع شماره ۶',
    date: '1404-10-12',
    time: '08:00',
    endTime: '12:00',
    type: 'exam',
    priority: 'high',
    subject: 'عمومی',
    location: 'آنلاین',
  },
  {
    id: '8',
    title: 'تحویل تمرین ریاضی',
    date: '1404-10-18',
    type: 'assignment',
    priority: 'medium',
    subject: 'ریاضی',
  },
  {
    id: '9',
    title: 'جلسه مشاوره تحصیلی',
    description: 'مشاوره با استاد راهنما',
    date: '1404-10-25',
    time: '11:00',
    type: 'class',
    priority: 'low',
  },
  {
    id: '10',
    title: 'کوییز فیزیک',
    date: '1404-10-28',
    time: '09:00',
    type: 'exam',
    priority: 'medium',
    subject: 'فیزیک',
  },
];

// توابع کمکی
export function getEventsForDate(date: string, events: CalendarEvent[] = MOCK_CALENDAR_EVENTS): CalendarEvent[] {
  return events.filter(event => event.date === date);
}

export function getUpcomingEvents(limit: number = 5, events: CalendarEvent[] = MOCK_CALENDAR_EVENTS): CalendarEvent[] {
  const today = '1404-10-07'; // Current date for mock
  return events
    .filter(event => event.date >= today)
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, limit);
}

export function generateMonthDays(year: number, month: number, events: CalendarEvent[] = MOCK_CALENDAR_EVENTS): CalendarDay[] {
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
      isToday: day === 7, // Today is 7th of دی
      isWeekend: dayIndex === 6, // جمعه
      events: getEventsForDate(dateStr, events),
    });
  }
  
  // Add days from next month to complete the grid
  const remainingDays = 42 - days.length; // 6 rows × 7 days
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

export function getEventsByType(type: EventType): CalendarEvent[] {
  return MOCK_CALENDAR_EVENTS.filter(e => e.type === type);
}

export function getHighPriorityEvents(): CalendarEvent[] {
  return MOCK_CALENDAR_EVENTS.filter(e => e.priority === 'high');
}
