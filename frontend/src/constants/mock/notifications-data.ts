/**
 * =============================================================================
 * NOTIFICATIONS MOCK DATA - داده‌های آزمایشی اعلان‌ها
 * =============================================================================
 * 
 * برای اتصال به Backend:
 * این داده‌ها را با API call به endpoint زیر جایگزین کنید:
 * GET /api/notifications
 * PUT /api/notifications/:id/read
 * DELETE /api/notifications/:id
 * 
 * =============================================================================
 */

export type NotificationType = 'info' | 'success' | 'warning' | 'error' | 'message' | 'alert';

export interface Notification {
  id: string;
  title: string;
  message: string;
  type: NotificationType;
  isRead: boolean;
  createdAt: string;
  time?: string; // برای نمایش زمان نسبی
  link?: string;
}

export const MOCK_NOTIFICATIONS: Notification[] = [
  {
    id: '1',
    title: 'تمرین جدید',
    message: 'تمرین جدیدی برای درس ریاضی منتشر شد.',
    type: 'info',
    isRead: false,
    createdAt: '2025-12-28T10:30:00',
    time: '۱۰ دقیقه پیش',
    link: '/classes',
  },
  {
    id: '2',
    title: 'نمره اعلام شد',
    message: 'نمره آزمون فیزیک شما ثبت شد: ۱۸ از ۲۰',
    type: 'success',
    isRead: false,
    createdAt: '2025-12-27T15:00:00',
    time: '۲ ساعت پیش',
  },
  {
    id: '3',
    title: 'یادآوری کلاس',
    message: 'کلاس آنلاین شیمی فردا ساعت ۱۰ صبح برگزار می‌شود.',
    type: 'warning',
    isRead: true,
    createdAt: '2025-12-26T18:00:00',
    time: '۱ روز پیش',
  },
  {
    id: '4',
    title: 'پاسخ تیکت',
    message: 'پشتیبانی به تیکت شما پاسخ داد.',
    type: 'info',
    isRead: true,
    createdAt: '2025-12-25T09:00:00',
    time: '۲ روز پیش',
    link: '/tickets',
  },
  {
    id: '5',
    title: 'مهلت تمرین',
    message: 'مهلت ارسال تمرین زبان انگلیسی تا فردا است.',
    type: 'error',
    isRead: false,
    createdAt: '2025-12-24T12:00:00',
    time: '۳ روز پیش',
  },
  {
    id: '6',
    title: 'تغییر زمان کلاس ریاضی',
    message: 'کلاس ریاضی فردا ساعت ۱۰ صبح برگزار می‌شود.',
    type: 'message',
    isRead: false,
    createdAt: '2025-12-23T14:00:00',
    time: '۴ روز پیش',
  },
  {
    id: '7',
    title: 'یادآوری آزمون',
    message: 'آزمون جامع هفته آینده برگزار خواهد شد.',
    type: 'alert',
    isRead: true,
    createdAt: '2025-12-22T10:00:00',
    time: '۵ روز پیش',
  },
];

// توابع کمکی
export function getUnreadNotifications(): Notification[] {
  return MOCK_NOTIFICATIONS.filter(n => !n.isRead);
}

export function getUnreadCount(): number {
  return MOCK_NOTIFICATIONS.filter(n => !n.isRead).length;
}

export function getNotificationById(id: string): Notification | undefined {
  return MOCK_NOTIFICATIONS.find(n => n.id === id);
}
