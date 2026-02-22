import type {
  AdminAnalyticsStat,
  AdminChartData,
  AdminDistributionData,
  AdminNotificationSettings,
  AdminProfileSettings,
  AdminRecentActivity,
  AdminSecuritySettings,
  MessageRecipient,
  Ticket,
} from '@/types';

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

// ---------------------------------------------------------------------------
// Persian number helpers
// ---------------------------------------------------------------------------

function toPersianDigits(n: number | string): string {
  return String(n).replace(/\d/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[Number(d)]);
}

function formatPersianNumber(n: number): string {
  return toPersianDigits(n.toLocaleString('en-US'));
}

function formatPersianPercent(n: number): string {
  const sign = n >= 0 ? '+' : '';
  return `${toPersianDigits(sign + n)}٪`;
}

// Map activity type to icon / colour
const ACTIVITY_STYLE: Record<string, { icon: string; color: string; bg: string }> = {
  registration: { icon: 'user-plus', color: 'text-blue-500', bg: 'bg-blue-500/10' },
  class: { icon: 'book', color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
  broadcast: { icon: 'megaphone', color: 'text-amber-500', bg: 'bg-amber-500/10' },
  quiz: { icon: 'clipboard-check', color: 'text-purple-500', bg: 'bg-purple-500/10' },
};

function relativeTime(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'همین الان';
  if (mins < 60) return `${toPersianDigits(mins)} دقیقه پیش`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${toPersianDigits(hours)} ساعت پیش`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'دیروز';
  return `${toPersianDigits(days)} روز پیش`;
}

/**
 * Admin Service
 * Handles all data fetching for the admin dashboard and management.
 */
export const AdminService = {
  // ============================================================================
  // Analytics
  // ============================================================================

  getAnalyticsStats: async (): Promise<AdminAnalyticsStat[]> => {
    const raw = await requestJson<{
      total_students: number;
      total_teachers: number;
      active_classes: number;
      total_classes: number;
      recent_messages: number;
      recent_quiz_attempts: number;
      new_students_30d: number;
      student_change: number;
      llm_cost_this_month: number;
    }>('/admin/analytics/stats/');

    return [
      {
        title: 'کل دانش‌آموزان',
        value: formatPersianNumber(raw.total_students),
        change: formatPersianPercent(
          raw.total_students > 0
            ? Math.round((raw.student_change / Math.max(raw.total_students - raw.student_change, 1)) * 100)
            : 0,
        ),
        trend: raw.student_change >= 0 ? 'up' : 'down',
        icon: 'users',
      },
      {
        title: 'کلاس‌های فعال',
        value: formatPersianNumber(raw.active_classes),
        change: `${toPersianDigits(raw.total_classes)} کل`,
        trend: 'up',
        icon: 'book',
      },
      {
        title: 'معلمان',
        value: formatPersianNumber(raw.total_teachers),
        change: '',
        trend: 'up',
        icon: 'graduation',
      },
      {
        title: 'پیام‌های ماه',
        value: formatPersianNumber(raw.recent_messages),
        change: `${formatPersianNumber(raw.recent_quiz_attempts)} آزمون`,
        trend: 'up',
        icon: 'trending',
      },
    ];
  },

  getChartData: async (days = 14): Promise<AdminChartData[]> => {
    const raw = await requestJson<Array<{ date: string; count: number }>>(
      `/admin/analytics/chart/?days=${days}`,
    );
    const dayNames = ['یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه', 'شنبه'];
    return raw.map((item) => {
      const d = new Date(item.date);
      return { name: dayNames[d.getDay()] ?? item.date, students: item.count };
    });
  },

  getDistributionData: async (): Promise<AdminDistributionData[]> => {
    const raw = await requestJson<{
      by_pipeline_type: Array<{ pipeline_type: string; count: number }>;
      by_level: Array<{ level: string; count: number }>;
    }>('/admin/analytics/distribution/');

    const pipelineLabels: Record<string, string> = {
      youtube: 'یوتیوب',
      upload: 'آپلود',
      text: 'متن',
    };

    if (raw.by_pipeline_type.length) {
      return raw.by_pipeline_type.map((item) => ({
        name: pipelineLabels[item.pipeline_type] ?? item.pipeline_type,
        value: item.count,
      }));
    }
    return raw.by_level.map((item) => ({ name: item.level, value: item.count }));
  },

  getRecentActivities: async (): Promise<AdminRecentActivity[]> => {
    const raw = await requestJson<
      Array<{ id: string; type: string; user: string; action: string; time: string }>
    >('/admin/analytics/recent-activity/');

    return raw.map((item, idx) => {
      const style = ACTIVITY_STYLE[item.type] ?? ACTIVITY_STYLE.registration;
      return {
        id: idx + 1,
        type: item.type,
        user: item.user,
        action: item.action,
        time: relativeTime(item.time),
        icon: style.icon,
        color: style.color,
        bg: style.bg,
      };
    });
  },

  // ============================================================================
  // Tickets
  // ============================================================================

  getTickets: async (): Promise<Ticket[]> => {
    return requestJson<Ticket[]>('/admin/tickets/');
  },

  replyToTicket: async (ticketPk: number, content: string) => {
    return requestJson(`/admin/tickets/${ticketPk}/reply/`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  },

  updateTicket: async (ticketPk: number, data: { status?: string; priority?: string }) => {
    return requestJson(`/admin/tickets/${ticketPk}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  // ============================================================================
  // Broadcast
  // ============================================================================

  getMessageRecipients: async (): Promise<MessageRecipient[]> => {
    return requestJson<MessageRecipient[]>('/notifications/admin/recipients/', { method: 'GET' });
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
  // Admin Profile / Security / Notification Settings
  // ============================================================================

  getProfileSettings: async (): Promise<AdminProfileSettings> => {
    return requestJson<AdminProfileSettings>('/admin/settings/profile/');
  },

  getSecuritySettings: async (): Promise<AdminSecuritySettings> => {
    return requestJson<AdminSecuritySettings>('/admin/settings/security/');
  },

  getNotificationSettings: async (): Promise<AdminNotificationSettings> => {
    return requestJson<AdminNotificationSettings>('/admin/settings/notifications/');
  },

  updateProfileSettings: async (data: Partial<AdminProfileSettings>) => {
    return requestJson('/admin/settings/profile/', {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  updateSecuritySettings: async (data: Partial<AdminSecuritySettings>) => {
    return requestJson('/admin/settings/security/', {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  updateNotificationSettings: async (data: Partial<AdminNotificationSettings>) => {
    return requestJson('/admin/settings/notifications/', {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  // ============================================================================
  // Ops & Maintenance
  // ============================================================================

  getServerHealth: async () => {
    return requestJson<{
      status: string;
      uptime: string;
      cpu: number;
      memory: number;
      disk: number;
      incidentsThisMonth: number;
      lastIncident: string | null;
    }>('/admin/server/health/');
  },

  getMaintenanceTasks: async () => {
    return requestJson<
      Array<{ id: string; title: string; window: string; owner: string; status: string; detail?: string }>
    >('/admin/maintenance/tasks/');
  },

  getBackups: async () => {
    return requestJson<{
      db_size: string;
      table_count: number;
      backups: Array<{ id: string; createdAt: string; size: string; type: string; status: string }>;
      note: string;
    }>('/admin/backups/');
  },

  triggerBackup: async (_type: 'full' | 'incremental') => {
    return requestJson<{ success: boolean; message: string }>('/admin/backups/trigger/', {
      method: 'POST',
      body: JSON.stringify({ type: _type }),
    });
  },

  getServerSettings: async () => {
    return requestJson<{
      autoBackup: boolean;
      backupWindow: string;
      backupRetentionDays: number;
      maintenanceAutoApprove: boolean;
      alertEmail: string;
    }>('/admin/server/settings/');
  },

  updateServerSettings: async (data: Record<string, unknown>) => {
    const result = await requestJson<{
      autoBackup: boolean;
      backupWindow: string;
      backupRetentionDays: number;
      maintenanceAutoApprove: boolean;
      alertEmail: string;
    }>('/admin/server/settings/', {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
    return { success: true, data: result };
  },

  // ============================================================================
  // LLM Usage Analytics (Token Tracking)
  // ============================================================================

  getLLMUsageSummary: async (days = 30) => {
    return requestJson<{
      total_requests: number;
      successful_requests: number;
      failed_requests: number;
      total_input_tokens: number;
      total_output_tokens: number;
      total_tokens: number;
      total_cost_usd: number;
      avg_duration_ms: number;
      total_audio_input_tokens: number;
      total_cached_input_tokens: number;
      total_thinking_tokens: number;
      total_cost_toman: number | null;
      usdt_toman_rate: number | null;
    }>(`/admin/llm-usage/summary/?days=${days}`);
  },

  getLLMUsageByFeature: async (days = 30) => {
    return requestJson<Array<{
      feature: string;
      feature_label: string;
      count: number;
      total_tokens: number;
      total_cost_usd: number;
      avg_duration_ms: number;
    }>>(`/admin/llm-usage/by-feature/?days=${days}`);
  },

  getLLMUsageByUser: async (days = 30) => {
    return requestJson<Array<{
      user_id: number | null;
      username: string;
      full_name: string;
      role: string;
      count: number;
      total_tokens: number;
      total_cost_usd: number;
    }>>(`/admin/llm-usage/by-user/?days=${days}`);
  },

  getLLMUsageByProvider: async (days = 30) => {
    return requestJson<Array<{
      provider: string;
      count: number;
      total_tokens: number;
      total_cost_usd: number;
    }>>(`/admin/llm-usage/by-provider/?days=${days}`);
  },

  getLLMUsageDaily: async (days = 30) => {
    return requestJson<Array<{
      date: string;
      count: number;
      total_tokens: number;
      total_cost_usd: number;
    }>>(`/admin/llm-usage/daily/?days=${days}`);
  },

  getLLMUsageRecentLogs: async (limit = 100) => {
    return requestJson<Array<{
      id: number;
      user: string | null;
      feature: string;
      provider: string;
      model_name: string;
      input_tokens: number;
      output_tokens: number;
      total_tokens: number;
      audio_input_tokens: number;
      cached_input_tokens: number;
      thinking_tokens: number;
      estimated_cost_usd: number;
      duration_ms: number;
      success: boolean;
      created_at: string;
    }>>(`/admin/llm-usage/recent/?limit=${limit}`);
  },
};
