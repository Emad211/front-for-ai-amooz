// Mock data for notifications
export interface Notification {
  id: string;
  title: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  isRead: boolean;
  createdAt: string;
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
    link: '/classes',
  },
  {
    id: '2',
    title: 'نمره اعلام شد',
    message: 'نمره آزمون فیزیک شما ثبت شد: ۱۸ از ۲۰',
    type: 'success',
    isRead: false,
    createdAt: '2025-12-27T15:00:00',
  },
  {
    id: '3',
    title: 'یادآوری کلاس',
    message: 'کلاس آنلاین شیمی فردا ساعت ۱۰ صبح برگزار می‌شود.',
    type: 'warning',
    isRead: true,
    createdAt: '2025-12-26T18:00:00',
  },
  {
    id: '4',
    title: 'پاسخ تیکت',
    message: 'پشتیبانی به تیکت شما پاسخ داد.',
    type: 'info',
    isRead: true,
    createdAt: '2025-12-25T09:00:00',
    link: '/tickets',
  },
  {
    id: '5',
    title: 'مهلت تمرین',
    message: 'مهلت ارسال تمرین زبان انگلیسی تا فردا است.',
    type: 'error',
    isRead: false,
    createdAt: '2025-12-24T12:00:00',
  },
];
