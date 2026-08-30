import type { EventPriority, EventType } from '@/types';

export const EVENT_TYPE_CONFIG: Record<
  EventType,
  { label: string; color: string; bgColor: string; dot: string }
> = {
  exam: {
    label: 'آزمون',
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
    dot: 'bg-red-500',
  },
  assignment: {
    label: 'تکلیف',
    color: 'text-orange-500',
    bgColor: 'bg-orange-500/10',
    dot: 'bg-orange-500',
  },
  class: {
    label: 'کلاس',
    color: 'text-blue-500',
    bgColor: 'bg-blue-500/10',
    dot: 'bg-blue-500',
  },
  holiday: {
    label: 'تعطیلی',
    color: 'text-green-500',
    bgColor: 'bg-green-500/10',
    dot: 'bg-green-500',
  },
  reminder: {
    label: 'یادآوری',
    color: 'text-purple-500',
    bgColor: 'bg-purple-500/10',
    dot: 'bg-purple-500',
  },
  study_plan: {
    label: 'مطالعه',
    color: 'text-indigo-600 dark:text-indigo-400',
    bgColor: 'bg-indigo-500/10',
    dot: 'bg-indigo-500',
  },
  advisor_note: {
    label: 'برنامهٔ مشاور',
    color: 'text-teal-600 dark:text-teal-400',
    bgColor: 'bg-teal-500/10',
    dot: 'bg-teal-500',
  },
  challenge: {
    label: 'چالش',
    color: 'text-pink-500',
    bgColor: 'bg-pink-500/10',
    dot: 'bg-pink-500',
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
