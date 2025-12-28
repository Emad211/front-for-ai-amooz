export interface Notification {
  id: string;
  title: string;
  message: string;
  time: string;
  isRead: boolean;
  type: 'message' | 'alert' | 'info';
}

export const MOCK_NOTIFICATIONS: Notification[] = [
  {
    id: '1',
    title: 'تغییر زمان کلاس ریاضی',
    message: 'کلاس ریاضی فردا ساعت ۱۰ صبح برگزار می‌شود.',
    time: '۱۰ دقیقه پیش',
    isRead: false,
    type: 'message',
  },
  {
    id: '2',
    title: 'تمرین جدید بارگذاری شد',
    message: 'تمرین فصل سوم درس فیزیک در پنل شما قرار گرفت.',
    time: '۲ ساعت پیش',
    isRead: false,
    type: 'info',
  },
  {
    id: '3',
    title: 'یادآوری آزمون',
    message: 'آزمون جامع هفته آینده برگزار خواهد شد.',
    time: '۱ روز پیش',
    isRead: true,
    type: 'alert',
  },
];
