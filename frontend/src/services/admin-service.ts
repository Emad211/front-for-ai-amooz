import {
  MOCK_ANALYTICS_STATS, 
  MOCK_CHART_DATA, 
  MOCK_DISTRIBUTION_DATA, 
  MOCK_RECENT_ACTIVITIES,
  MOCK_TICKETS,
  MOCK_MESSAGE_RECIPIENTS,
  MOCK_ADMIN_PROFILE,
  MOCK_ADMIN_SECURITY,
  MOCK_ADMIN_NOTIFICATIONS,
} from '@/constants/mock';
import { 
  MOCK_SERVER_HEALTH,
  MOCK_BACKUPS,
  MOCK_MAINTENANCE_TASKS,
  MOCK_SERVER_SETTINGS,
} from '@/constants/mock';
import type { AdminNotificationSettings, AdminProfileSettings, AdminSecuritySettings, MessageRecipient } from '@/types';

const RAW_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');
const API_URL = RAW_API_URL.endsWith('/api') ? RAW_API_URL : `${RAW_API_URL}/api`;

function getAccessToken(): string {
  if (typeof window === 'undefined') {
    throw new Error('This action must run in the browser.');
  }
  const access = window.localStorage.getItem('ai_amooz_access');
  if (!access) {
    throw new Error('ابتدا وارد حساب کاربری شوید.');
  }
  return access;
}

async function parseJson(response: Response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function extractErrorMessage(payload: unknown, fallback: string) {
  if (payload && typeof payload === 'object') {
    const obj = payload as Record<string, unknown>;
    if (obj.errors && typeof obj.errors === 'object') {
      const entries = Object.entries(obj.errors as Record<string, unknown>)
        .map(([field, messages]) => {
          if (Array.isArray(messages)) {
            const joined = messages.map((m) => String(m)).join(', ');
            return field === 'non_field_errors' ? joined : `${field}: ${joined}`;
          }
          return `${field}: ${String(messages)}`;
        })
        .filter(Boolean);
      if (entries.length) return entries.join(' | ');
    }
    if (typeof obj.detail === 'string' && obj.detail.trim()) return obj.detail;
    if (typeof obj.message === 'string' && obj.message.trim()) return obj.message;
  }
  if (typeof payload === 'string' && payload.trim()) return payload;
  return fallback;
}

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }

  const headers = new Headers(options.headers);
  if (!headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${getAccessToken()}`);
  }
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json');
  }

  const url = `${API_URL}${path}`;

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch {
    throw new Error(
      `ارتباط با سرور برقرار نشد. (آدرس فعلی API: ${RAW_API_URL})` +
        ' معمولاً یکی از این‌هاست: بک‌اند اجرا نیست، آدرس/پورت اشتباه است، یا مرورگر به خاطر CORS/Mixed Content درخواست را بلاک کرده.'
    );
  }

  const payload = await parseJson(response);
  if (!response.ok) {
    const message = extractErrorMessage(payload, 'درخواست ناموفق بود.');
    throw new Error(message);
  }
  return payload as T;
}

/**
 * Admin Service
 * Handles all data fetching for the admin dashboard and management.
 */
export const AdminService = {
  getAnalyticsStats: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_ANALYTICS_STATS;
  },

  getChartData: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_CHART_DATA;
  },

  getDistributionData: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_DISTRIBUTION_DATA;
  },

  getRecentActivities: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_RECENT_ACTIVITIES;
  },

  getTickets: async () => {
    await new Promise(resolve => setTimeout(resolve, 600));
    return MOCK_TICKETS;
  },

  getMessageRecipients: async (): Promise<MessageRecipient[]> => {
    try {
      return await requestJson<MessageRecipient[]>('/notifications/admin/recipients/', { method: 'GET' });
    } catch {
      return MOCK_MESSAGE_RECIPIENTS as MessageRecipient[];
    }
  },

  getProfileSettings: async (): Promise<AdminProfileSettings> => {
    await new Promise(resolve => setTimeout(resolve, 400));
    return MOCK_ADMIN_PROFILE;
  },

  getSecuritySettings: async (): Promise<AdminSecuritySettings> => {
    await new Promise(resolve => setTimeout(resolve, 400));
    return MOCK_ADMIN_SECURITY;
  },

  getNotificationSettings: async (): Promise<AdminNotificationSettings> => {
    await new Promise(resolve => setTimeout(resolve, 400));
    return MOCK_ADMIN_NOTIFICATIONS;
  },

  updateProfileSettings: async (data: Partial<AdminProfileSettings>) => {
    await new Promise(resolve => setTimeout(resolve, 800));
    return { success: true, data };
  },

  updateSecuritySettings: async (data: Partial<AdminSecuritySettings>) => {
    await new Promise(resolve => setTimeout(resolve, 800));
    return { success: true, data };
  },

  updateNotificationSettings: async (data: Partial<AdminNotificationSettings>) => {
    await new Promise(resolve => setTimeout(resolve, 800));
    return { success: true, data };
  },

  sendBroadcastNotification: async (payload: {
    title: string;
    message: string;
    audience: 'all' | 'students' | 'teachers';
    notification_type?: 'info' | 'success' | 'warning' | 'error' | 'message' | 'alert';
  }) => {
    return requestJson('/notifications/admin/broadcast/', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  // ============================================================================
  // Ops & Maintenance
  // ============================================================================

  getServerHealth: async () => {
    await new Promise(resolve => setTimeout(resolve, 300));
    return MOCK_SERVER_HEALTH;
  },

  getMaintenanceTasks: async () => {
    await new Promise(resolve => setTimeout(resolve, 400));
    return MOCK_MAINTENANCE_TASKS;
  },

  getBackups: async () => {
    await new Promise(resolve => setTimeout(resolve, 350));
    return MOCK_BACKUPS;
  },

  triggerBackup: async (type: 'full' | 'incremental') => {
    await new Promise(resolve => setTimeout(resolve, 600));
    return { success: true, type, id: `new-${Date.now()}` };
  },

  getServerSettings: async () => {
    await new Promise(resolve => setTimeout(resolve, 300));
    return MOCK_SERVER_SETTINGS;
  },

  updateServerSettings: async (data: Partial<typeof MOCK_SERVER_SETTINGS>) => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return { success: true, data: { ...MOCK_SERVER_SETTINGS, ...data } };
  },
};
