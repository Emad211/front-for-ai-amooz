// Mock data for tickets
export type TicketStatus = 'open' | 'pending' | 'answered' | 'closed';
export type TicketPriority = 'low' | 'medium' | 'high';

export interface TicketMessage {
  id: string;
  content: string;
  isAdmin: boolean;
  createdAt: string;
  attachments?: string[];
}

export interface Ticket {
  id: string;
  subject: string;
  status: TicketStatus;
  priority: TicketPriority;
  department: string;
  createdAt: string;
  updatedAt: string;
  messages: TicketMessage[];
  userId?: string;
  userName?: string;
  userEmail?: string;
}

export const MOCK_TICKETS: Ticket[] = [
  {
    id: 'TKT-001',
    subject: 'مشکل در پخش ویدیو درس ریاضی',
    status: 'answered',
    priority: 'medium',
    department: 'پشتیبانی فنی',
    createdAt: '2025-12-26T10:30:00',
    updatedAt: '2025-12-27T14:00:00',
    userId: 'user-1',
    userName: 'علی محمدی',
    userEmail: 'ali@example.com',
    messages: [
      {
        id: 'm1',
        content: 'سلام، ویدیوهای درس ریاضی برای من پخش نمی‌شود و خطای ۴۰۴ می‌دهد.',
        isAdmin: false,
        createdAt: '2025-12-26T10:30:00',
      },
      {
        id: 'm2',
        content: 'سلام، مشکل شما بررسی و برطرف شد. لطفاً صفحه را رفرش کنید.',
        isAdmin: true,
        createdAt: '2025-12-27T14:00:00',
      },
    ],
  },
  {
    id: 'TKT-002',
    subject: 'درخواست دسترسی به کلاس جدید',
    status: 'open',
    priority: 'low',
    department: 'آموزش',
    createdAt: '2025-12-27T09:00:00',
    updatedAt: '2025-12-27T09:00:00',
    userId: 'user-2',
    userName: 'سارا احمدی',
    userEmail: 'sara@example.com',
    messages: [
      {
        id: 'm3',
        content: 'سلام، می‌خواستم در کلاس فیزیک آقای کریمی ثبت‌نام کنم ولی دسترسی ندارم.',
        isAdmin: false,
        createdAt: '2025-12-27T09:00:00',
      },
    ],
  },
  {
    id: 'TKT-003',
    subject: 'مشکل در پرداخت اشتراک',
    status: 'pending',
    priority: 'high',
    department: 'مالی',
    createdAt: '2025-12-25T16:00:00',
    updatedAt: '2025-12-26T11:00:00',
    userId: 'user-3',
    userName: 'رضا کریمی',
    userEmail: 'reza@example.com',
    messages: [
      {
        id: 'm4',
        content: 'پرداخت انجام شده ولی اشتراکم فعال نشده است.',
        isAdmin: false,
        createdAt: '2025-12-25T16:00:00',
      },
      {
        id: 'm5',
        content: 'لطفاً شماره پیگیری تراکنش را ارسال کنید.',
        isAdmin: true,
        createdAt: '2025-12-26T11:00:00',
      },
    ],
  },
  {
    id: 'TKT-004',
    subject: 'پیشنهاد افزودن قابلیت جدید',
    status: 'closed',
    priority: 'low',
    department: 'پیشنهادات',
    createdAt: '2025-12-20T12:00:00',
    updatedAt: '2025-12-22T09:00:00',
    userId: 'user-1',
    userName: 'علی محمدی',
    userEmail: 'ali@example.com',
    messages: [
      {
        id: 'm6',
        content: 'پیشنهاد می‌کنم قابلیت دانلود ویدیوها اضافه شود.',
        isAdmin: false,
        createdAt: '2025-12-20T12:00:00',
      },
      {
        id: 'm7',
        content: 'ممنون از پیشنهاد شما. این قابلیت در نسخه بعدی اضافه خواهد شد.',
        isAdmin: true,
        createdAt: '2025-12-22T09:00:00',
      },
    ],
  },
];

export const TICKET_DEPARTMENTS = [
  'پشتیبانی فنی',
  'آموزش',
  'مالی',
  'پیشنهادات',
  'سایر',
];
