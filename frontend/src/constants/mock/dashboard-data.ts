/**
 * =============================================================================
 * DASHBOARD MOCK DATA - داده‌های آزمایشی داشبورد
 * =============================================================================
 * 
 * برای اتصال به Backend:
 * این داده‌ها را با API call به endpoint زیر جایگزین کنید:
 * GET /api/dashboard/stats
 * GET /api/dashboard/activities
 * GET /api/dashboard/events
 * 
 * =============================================================================
 */

export interface DashboardStats {
  activeCourses: number;
  totalCourses: number;
  completionPercent: number;
  averageScore: number;
  studyHours: string;
  studyMinutes: string;
}

export interface DashboardActivity {
  id: string;
  title: string;
  time: string;
  type: 'در حال انجام' | 'ویدیو' | 'آزمون' | 'تکلیف';
  icon: 'file' | 'video' | 'book' | 'pen';
}

export interface DashboardEvent {
  id: string;
  title: string;
  status: string;
  date: string;
  month: string;
  icon: 'clock' | 'file';
}

export const MOCK_DASHBOARD_STATS: DashboardStats = {
  activeCourses: 5,
  totalCourses: 8,
  completionPercent: 75,
  averageScore: 75,
  studyHours: '۱۲',
  studyMinutes: '۳۰',
};

export const MOCK_ACTIVITIES: DashboardActivity[] = [
  {
    id: '1',
    title: 'ریاضیات گسسته - فصل ۲',
    time: '۲ ساعت پیش',
    type: 'در حال انجام',
    icon: 'file',
  },
  {
    id: '2',
    title: 'فیزیک کوانتوم - مقدمه',
    time: 'دیروز',
    type: 'ویدیو',
    icon: 'video',
  },
  {
    id: '3',
    title: 'زبان انگلیسی تخصصی',
    time: '۳ روز پیش',
    type: 'آزمون',
    icon: 'book',
  },
];

export const MOCK_UPCOMING_EVENTS: DashboardEvent[] = [
  {
    id: '1',
    title: 'آزمون میان‌ترم ریاضی',
    status: 'ساعت ۱۰:۰۰ - آنلاین',
    date: '۱۵',
    month: 'تیر',
    icon: 'clock',
  },
  {
    id: '2',
    title: 'تحویل پروژه فیزیک',
    status: 'تا پایان روز',
    date: '۲۰',
    month: 'تیر',
    icon: 'file',
  },
];

// توابع کمکی
export function getProgressPercent(): number {
  return Math.round((MOCK_DASHBOARD_STATS.activeCourses / MOCK_DASHBOARD_STATS.totalCourses) * 100);
}
