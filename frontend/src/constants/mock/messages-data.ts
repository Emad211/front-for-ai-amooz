/**
 * =============================================================================
 * MESSAGES MOCK DATA - داده‌های آزمایشی پیام‌ها
 * =============================================================================
 * 
 * برای اتصال به Backend:
 * این داده‌ها را با API call به endpoint زیر جایگزین کنید:
 * POST /api/messages
 * GET /api/messages/stats
 * 
 * =============================================================================
 */

export interface MessageRecipient {
  id: string;
  name: string;
  email: string;
  avatar?: string;
}

export interface Message {
  id: string;
  subject: string;
  content: string;
  recipients: MessageRecipient[];
  sentAt: string;
  status: 'sent' | 'pending' | 'failed';
}

export interface MessageStats {
  totalSent: number;
  thisMonth: number;
  responseRate: number;
}

// لیست گیرندگان برای فرم ارسال پیام
export const MOCK_MESSAGE_RECIPIENTS: MessageRecipient[] = [
  { id: '1', name: 'علی محمدی', email: 'ali@example.com', avatar: '/avatars/01.png' },
  { id: '2', name: 'سارا احمدی', email: 'sara@example.com', avatar: '/avatars/02.png' },
  { id: '3', name: 'رضا کریمی', email: 'reza@example.com', avatar: '/avatars/03.png' },
  { id: '4', name: 'مریم حسینی', email: 'maryam@example.com', avatar: '/avatars/04.png' },
  { id: '5', name: 'امیر رضایی', email: 'amir@example.com', avatar: '/avatars/05.png' },
  { id: '6', name: 'زهرا نوری', email: 'zahra@example.com', avatar: '/avatars/06.png' },
  { id: '7', name: 'محمد کاظمی', email: 'mohammad@example.com', avatar: '/avatars/07.png' },
  { id: '8', name: 'فاطمه موسوی', email: 'fatemeh@example.com', avatar: '/avatars/08.png' },
];

export const MOCK_MESSAGE_STATS: MessageStats = {
  totalSent: 156,
  thisMonth: 23,
  responseRate: 87,
};

// توابع کمکی
export function searchRecipients(query: string): MessageRecipient[] {
  const lowerQuery = query.toLowerCase();
  return MOCK_MESSAGE_RECIPIENTS.filter(r => 
    r.name.toLowerCase().includes(lowerQuery) ||
    r.email.toLowerCase().includes(lowerQuery)
  );
}
