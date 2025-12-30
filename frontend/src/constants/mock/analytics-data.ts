/**
 * =============================================================================
 * ANALYTICS MOCK DATA - داده‌های آزمایشی تحلیل و آمار
 * =============================================================================
 */

import type { AdminAnalyticsStat } from "@/types";

export const MOCK_ANALYTICS_STATS: AdminAnalyticsStat[] = [
  {
    title: 'کل دانش‌آموزان',
    value: '۱,۲۸۴',
    change: '+۱۲٪',
    trend: 'up',
    icon: 'users',
  },
  {
    title: 'کلاس‌های فعال',
    value: '۴۲',
    change: '+۳',
    trend: 'up',
    icon: 'book',
  },
  {
    title: 'فارغ‌التحصیلان',
    value: '۱۵۶',
    change: '+۸٪',
    trend: 'up',
    icon: 'graduation',
  },
  {
    title: 'نرخ تعامل',
    value: '۸۴٪',
    change: '+۵٪',
    trend: 'up',
    icon: 'trending',
  },
];

export const MOCK_RECENT_ACTIVITIES = [
  {
    id: 1,
    type: 'registration',
    user: 'سارا احمدی',
    action: 'در کلاس فیزیک ثبت‌نام کرد',
    time: '۱۰ دقیقه پیش',
    icon: 'user-plus',
    color: 'text-blue-500',
    bg: 'bg-blue-500/10',
  },
  {
    id: 2,
    type: 'class',
    user: 'مدیر',
    action: 'کلاس جدید "شیمی آلی" را ایجاد کرد',
    time: '۲ ساعت پیش',
    icon: 'book',
    color: 'text-emerald-500',
    bg: 'bg-emerald-500/10',
  },
  {
    id: 3,
    type: 'message',
    user: 'علی محمدی',
    action: 'یک پیام جدید ارسال کرد',
    time: '۵ ساعت پیش',
    icon: 'message',
    color: 'text-amber-500',
    bg: 'bg-amber-500/10',
  },
  {
    id: 4,
    type: 'award',
    user: 'رضا کریمی',
    action: 'دوره ریاضی پیشرفته را به پایان رساند',
    time: 'دیروز',
    icon: 'award',
    color: 'text-purple-500',
    bg: 'bg-purple-500/10',
  },
];

export const MOCK_CHART_DATA = [
  { name: 'شنبه', students: 40 },
  { name: 'یکشنبه', students: 30 },
  { name: 'دوشنبه', students: 65 },
  { name: 'سه‌شنبه', students: 45 },
  { name: 'چهارشنبه', students: 90 },
  { name: 'پنج‌شنبه', students: 75 },
  { name: 'جمعه', students: 55 },
];

export const MOCK_DISTRIBUTION_DATA = [
  { name: 'ریاضی', value: 35 },
  { name: 'فیزیک', value: 25 },
  { name: 'شیمی', value: 20 },
  { name: 'زیست', value: 20 },
];

export const CHART_COLORS = [
  'hsl(var(--primary))',
  '#6366f1',
  '#8b5cf6',
  '#ec4899',
];
