import type { EventPriority, EventType } from '@/types';

export const EVENT_TYPE_CONFIG: Record<EventType, { label: string; color: string; bgColor: string }> = {
  exam: {
    label: 'آزمون',
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
  },
  assignment: {
    label: 'تکلیف',
    color: 'text-orange-500',
    bgColor: 'bg-orange-500/10',
  },
  class: {
    label: 'کلاس',
    color: 'text-blue-500',
    bgColor: 'bg-blue-500/10',
  },
  holiday: {
    label: 'تعطیلی',
    color: 'text-green-500',
    bgColor: 'bg-green-500/10',
  },
  reminder: {
    label: 'یادآوری',
    color: 'text-purple-500',
    bgColor: 'bg-purple-500/10',
  },
};

export const PERSIAN_MONTHS = [
  'فروردین',
  'اردیبهشت',
  'خرداد',
  'تیر',
  'مرداد',
  'شهریور',
  'مهر',
  'آبان',
  'آذر',
  'دی',
  'بهمن',
  'اسفند',
];

export const PERSIAN_WEEKDAYS = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه'];

export const PERSIAN_WEEKDAYS_SHORT = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج'];

export const EVENT_PRIORITIES: Array<{ value: EventPriority; label: string }> = [
  { value: 'high', label: 'بالا' },
  { value: 'medium', label: 'متوسط' },
  { value: 'low', label: 'کم' },
];
