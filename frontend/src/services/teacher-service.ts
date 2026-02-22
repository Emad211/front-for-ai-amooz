import type {
  AdminAnalyticsStat,
  AdminChartData,
  AdminDistributionData,
  AdminRecentActivity,
  AdminProfileSettings,
  AdminSecuritySettings,
  AdminNotificationSettings,
  ClassDetail,
  Course,
  Student,
  Notification,
} from '@/types';

import {
  courseStructureToChapters,
  courseStructureToObjectives,
  parseCourseStructure,
} from '@/lib/classes/course-structure';

import {
  clearAuthStorage,
  refreshAccessToken,
} from '@/services/auth-service';

type AuthMeResponse = {
  id: number;
  username: string;
  first_name?: string;
  last_name?: string;
  email: string;
  phone?: string | null;
  avatar?: string | null;
  role: string;
  is_profile_completed: boolean;
  bio?: string | null;
  location?: string | null;
};

type ClassCreationSessionListItem = {
  id: number;
  status: string;
  title: string;
  description: string;
  level?: string;
  duration?: string;
  is_published?: boolean;
  invites_count?: number;
  lessons_count?: number;
  organization_id?: number | null;
  created_at: string;
  updated_at: string;
};

type ClassInvite = {
  id: number;
  phone: string;
  invite_code: string;
  created_at: string;
};

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

  const doFetch = async (reqHeaders: Headers) => {
    try {
      return await fetch(url, { ...options, headers: reqHeaders });
    } catch {
      throw new Error(
        `ارتباط با سرور برقرار نشد. (آدرس فعلی API: ${RAW_API_URL})` +
          ' معمولاً یکی از این‌هاست: بک‌اند اجرا نیست، آدرس/پورت اشتباه است، یا مرورگر به خاطر CORS/Mixed Content درخواست را بلاک کرده.'
      );
    }
  };

  let response = await doFetch(headers);
  let payload = await parseJson(response);

  // Auto-refresh on 401 if we had an Authorization header
  if (response.status === 401 && headers.has('Authorization')) {
    try {
      const newAccess = await refreshAccessToken();
      headers.set('Authorization', `Bearer ${newAccess}`);
      response = await doFetch(headers);
      payload = await parseJson(response);
    } catch {
      // refreshAccessToken already handles redirect/storage cleanup
    }
  }

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, response.statusText));
  }
  return payload as T;
}

export const TeacherService = {
  getAnalyticsStats: async (days?: number): Promise<AdminAnalyticsStat[]> => {
    const url = days ? `/classes/teacher/analytics/stats/?days=${days}` : '/classes/teacher/analytics/stats/';
    return requestJson<AdminAnalyticsStat[]>(url, { method: 'GET' });
  },

  getChartData: async (days?: number): Promise<AdminChartData[]> => {
    const url = days ? `/classes/teacher/analytics/chart/?days=${days}` : '/classes/teacher/analytics/chart/';
    return requestJson<AdminChartData[]>(url, { method: 'GET' });
  },

  getDistributionData: async (days?: number): Promise<AdminDistributionData[]> => {
    const url = days ? `/classes/teacher/analytics/distribution/?days=${days}` : '/classes/teacher/analytics/distribution/';
    return requestJson<AdminDistributionData[]>(url, { method: 'GET' });
  },

  getRecentActivities: async (): Promise<AdminRecentActivity[]> => {
    return requestJson<AdminRecentActivity[]>('/classes/teacher/analytics/activities/', { method: 'GET' });
  },

  exportAnalyticsCSV: async (days: number = 7) => {
    const response = await fetch(`${API_URL}/classes/teacher/analytics/export-csv/?days=${days}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${getAccessToken()}`,
      },
    });
    if (!response.ok) throw new Error('Export failed');
    return response.blob();
  },

  getStudents: async () => {
    return requestJson<Student[]>('/classes/teacher/students/', { method: 'GET' });
  },

  getCourses: async (organizationId?: number | null) => {
    const orgParam = organizationId ? `?organization=${organizationId}` : '?organization=personal';
    const sessions = await requestJson<ClassCreationSessionListItem[]>(`/classes/creation-sessions/${orgParam}`, { method: 'GET' });
    const courses: Course[] = sessions.map((s) => ({
      id: s.id,
      title: s.title,
      description: s.description,
      tags: [],
      status: s.is_published ? 'active' : 'draft',
      createdAt: s.created_at,
      lastActivity: s.updated_at,
      studentsCount: Number(s.invites_count ?? 0) || 0,
      lessonsCount: Number(s.lessons_count ?? 0) || 0,
      level: (s.level as any) || undefined,
      duration: s.duration || undefined,
    }));
    return courses;
  },

  getMessageRecipients: async () => {
    return [];
  },

  getProfileSettings: async (): Promise<AdminProfileSettings> => {
    const me = await requestJson<AuthMeResponse>('/accounts/me/', { method: 'GET' });
    const first = (me.first_name || '').trim();
    const last = (me.last_name || '').trim();
    const fullName = `${first} ${last}`.trim() || first || me.username;
    return {
      name: fullName,
      email: me.email || '',
      phone: me.phone || '',
      bio: me.bio || '',
      location: me.location || '',
      avatar: (me.avatar as unknown as string) || '',
    };
  },

  getSecuritySettings: async (): Promise<AdminSecuritySettings> => {
    return {
      twoFactorEnabled: false,
      lastPasswordChange: '',
    };
  },

  getNotificationSettings: async (): Promise<AdminNotificationSettings> => {
    return {
      emailNotifications: false,
      browserNotifications: false,
      smsNotifications: false,
      marketingEmails: false,
    };
  },

  updateProfileSettings: async (data: Partial<AdminProfileSettings>) => {
    // Map UI 'name' to first_name/last_name; keep it simple for Persian names.
    const payload: Record<string, unknown> = {};
    if (typeof data.name === 'string') {
      const normalized = data.name.trim().replace(/\s+/g, ' ');
      const parts = normalized ? normalized.split(' ') : [];
      if (parts.length <= 1) {
        payload.first_name = normalized;
        payload.last_name = '';
      } else {
        payload.last_name = parts[parts.length - 1];
        payload.first_name = parts.slice(0, -1).join(' ');
      }
    }
    
    // Add all supported fields for update
    if (typeof data.email === 'string') payload.email = data.email;
    if (typeof data.phone === 'string') payload.phone = data.phone;
    if (typeof data.avatar === 'string') payload.avatar = data.avatar;
    if (typeof data.bio === 'string') payload.bio = data.bio;
    if (typeof data.location === 'string') payload.location = data.location;

    await requestJson<AuthMeResponse>('/accounts/me/', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });

    return { success: true };
  },

  updateSecuritySettings: async (data: Partial<AdminSecuritySettings>) => {
    return { success: false, data };
  },

  updateNotificationSettings: async (data: Partial<AdminNotificationSettings>) => {
    return { success: false, data };
  },

  getNotifications: async (): Promise<Notification[]> => {
    return requestJson<Notification[]>('/notifications/teacher/', { method: 'GET' });
  },

  markNotificationRead: async (id: string) => {
    return requestJson<any>(`/notifications/${encodeURIComponent(id)}/read/`, { method: 'POST' });
  },

  markAllNotificationsRead: async () => {
    return requestJson<any>(`/notifications/read-all/`, { method: 'POST' });
  },

  getClassDetail: async (classId: string): Promise<ClassDetail | null> => {
    const id = Number(classId);
    if (!Number.isFinite(id)) return null;
    const session = await requestJson<any>(`/classes/creation-sessions/${id}/`, { method: 'GET' });

    const structure = parseCourseStructure(session.structure_json);
    const objectives = courseStructureToObjectives(structure);
    const isPublished = Boolean(session.is_published);
    const chapters = courseStructureToChapters(structure, { isPublished });

    return {
      id: session.id,
      title: session.title,
      description: session.description,
      tags: [],
      status: isPublished ? 'active' : 'draft',
      createdAt: session.created_at,
      lastActivity: session.updated_at,
      level: session.level || undefined,
      duration: session.duration || undefined,
      pipelineStatus: session.status,
      transcriptMarkdown: session.transcript_markdown,
      structureJson: session.structure_json,
      pipelineErrorDetail: session.error_detail,
      objectives,
      studentsCount: Number(session.invites_count ?? 0) || 0,
      lessonsCount: chapters.reduce((acc, ch) => acc + ch.lessons.length, 0),
      chapters,
      enrolledStudents: [],
      announcements: [],
      schedule: [],
    };
  },

  getClassStudents: async (classId: string) => {
    const id = Number(classId);
    if (!Number.isFinite(id)) return [];
    const invites = await requestJson<ClassInvite[]>(`/classes/creation-sessions/${id}/invites/`, { method: 'GET' });
    return invites.map((inv) => ({
      id: String(inv.id),
      name: inv.phone,
      email: inv.invite_code,
      avatar: '',
      joinDate: inv.created_at,
      progress: 0,
      lastActivity: inv.created_at,
      status: 'inactive' as const,
    }));
  },

  updateClass: async (classId: string, data: Partial<Course>) => {
    const id = Number(classId);
    if (!Number.isFinite(id)) return { success: false, data: { id: classId, ...data } };

    const payload: Record<string, unknown> = {};
    if (typeof (data as any).title === 'string') payload.title = (data as any).title;
    if (typeof (data as any).description === 'string') payload.description = (data as any).description;
    if (typeof (data as any).structureJson === 'string') payload.structure_json = (data as any).structureJson;
    if (typeof (data as any).level === 'string') payload.level = (data as any).level;
    if (typeof (data as any).duration === 'string') payload.duration = (data as any).duration;

    await requestJson(`/classes/creation-sessions/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });

    return { success: true, data: { id: classId, ...data } };
  },

  deleteClass: async (classId: string) => {
    const id = Number(classId);
    if (Number.isFinite(id)) {
      await requestJson<void>(`/classes/creation-sessions/${id}/`, { method: 'DELETE' });
      return { success: true, classId };
    }
    return { success: false, classId };
  },

  removeStudentFromClass: async (classId: string, studentId: string) => {
    const id = Number(classId);
    const inviteId = Number(studentId);
    if (!Number.isFinite(id) || !Number.isFinite(inviteId)) return { success: false, classId, studentId };
    await requestJson<void>(`/classes/creation-sessions/${id}/invites/${inviteId}/`, { method: 'DELETE' });
    return { success: true, classId, studentId };
  },

  addStudentToClass: async (classId: string, studentEmail: string) => {
    return { success: false, classId, studentEmail };
  },
};
