import {
  MOCK_DASHBOARD_STATS,
  MOCK_ACTIVITIES,
  MOCK_UPCOMING_EVENTS,
  MOCK_TICKETS,
  MOCK_NOTIFICATIONS,
  MOCK_CALENDAR_EVENTS,
} from '@/constants/mock';
import type { Course, CourseContent, UserProfile } from '@/types';
import { clearAuthStorage, getStoredTokens, persistTokens, persistUser, refreshAccessToken } from '@/services/auth-service';

const RAW_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');
const API_URL = RAW_API_URL.endsWith('/api') ? RAW_API_URL : `${RAW_API_URL}/api`;
const BASE_URL = RAW_API_URL.replace(/\/api$/, '');

function getAccessToken(): string {
  if (typeof window === 'undefined') {
    throw new Error('This action must run in the browser.');
  }
  const access = window.localStorage.getItem('ai_amooz_access');
  const trimmed = (access || '').trim();
  if (!trimmed || trimmed === 'undefined' || trimmed === 'null') {
    throw new Error('ابتدا وارد حساب کاربری شوید.');
  }
  return trimmed;
}

function navigateToLogin() {
  if (typeof window === 'undefined') return;
  // Avoid endless loops if already on login.
  if (window.location.pathname.startsWith('/login')) return;
  window.location.href = '/login';
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
    if (typeof obj.detail === 'string') return obj.detail;
    if (typeof obj.message === 'string') return obj.message;
  }
  if (Array.isArray(payload)) {
    return payload.map((item) => String(item)).join(', ');
  }
  if (typeof payload === 'string' && payload.trim()) {
    const s = payload.trim();
    // If server returned an HTML error page, don't dump it into the chat UI.
    if (/^<!doctype\s+html/i.test(s) || /<html[\s>]/i.test(s)) {
      return 'خطای داخلی سرور رخ داد. لطفاً چند لحظه بعد دوباره تلاش کنید.';
    }
    return s;
  }
  return fallback;
}

async function requestJson<T>(url: string, options: RequestInit): Promise<T> {
  const doFetch = async (reqOptions: RequestInit) => {
    try {
      return await fetch(url, reqOptions);
    } catch {
      throw new Error(
        `ارتباط با سرور برقرار نشد. (آدرس فعلی API: ${RAW_API_URL})` +
          ' معمولاً یکی از این‌هاست: بک‌اند اجرا نیست، آدرس/پورت اشتباه است، یا مرورگر به خاطر CORS/Mixed Content درخواست را بلاک کرده.'
      );
    }
  };

  const headers = new Headers(options.headers);

  let response = await doFetch({ ...options, headers });
  let payload = await parseJson(response);

  // If access token is invalid/expired, try a single refresh and retry.
  if (response.status === 401) {
    const hadAuth = headers.has('Authorization');
    if (hadAuth) {
      try {
        const newAccess = await refreshAccessToken();
        headers.set('Authorization', `Bearer ${newAccess}`);
        response = await doFetch({ ...options, headers });
        payload = await parseJson(response);
      } catch {
        // refreshAccessToken already handled redirect/storage.
      }
    }
  }

  if (!response.ok) {
    const message = extractErrorMessage(payload, response.statusText);
    // If server says token is invalid, clear and redirect.
    if (response.status === 401 && typeof message === 'string' && message.includes('token')) {
      clearAuthStorage();
      navigateToLogin();
    }
    throw new Error(message);
  }
  return payload as T;
}

async function requestBlob(url: string, options: RequestInit): Promise<Blob> {
  const doFetch = async (reqOptions: RequestInit) => {
    try {
      return await fetch(url, reqOptions);
    } catch {
      throw new Error(
        `ارتباط با سرور برقرار نشد. (آدرس فعلی API: ${RAW_API_URL})` +
          ' معمولاً یکی از این‌هاست: بک‌اند اجرا نیست، آدرس/پورت اشتباه است، یا مرورگر به خاطر CORS/Mixed Content درخواست را بلاک کرده.'
      );
    }
  };

  const headers = new Headers(options.headers);

  let response = await doFetch({ ...options, headers });

  if (response.status === 401) {
    const hadAuth = headers.has('Authorization');
    if (hadAuth) {
      try {
        const newAccess = await refreshAccessToken();
        headers.set('Authorization', `Bearer ${newAccess}`);
        response = await doFetch({ ...options, headers });
      } catch {
        // refreshAccessToken already handled redirect/storage.
      }
    }
  }

  if (!response.ok) {
    // IMPORTANT: a Response body can only be read once.
    // We return `response.blob()` on success, so only attempt to parse a cloned response for error messaging.
    let payload: unknown = null;
    try {
      payload = await parseJson(response.clone());
    } catch {
      payload = null;
    }

    const message = extractErrorMessage(payload, response.statusText);
    if (response.status === 401 && typeof message === 'string' && message.includes('token')) {
      clearAuthStorage();
      navigateToLogin();
    }
    throw new Error(message);
  }

  return response.blob();
}

async function requestFormData<T>(url: string, options: RequestInit): Promise<T> {
  const doFetch = async (reqOptions: RequestInit) => {
    try {
      return await fetch(url, reqOptions);
    } catch {
      throw new Error(
        `ارتباط با سرور برقرار نشد. (آدرس فعلی API: ${RAW_API_URL})` +
          ' معمولاً یکی از این‌هاست: بک‌اند اجرا نیست، آدرس/پورت اشتباه است، یا مرورگر به خاطر CORS/Mixed Content درخواست را بلاک کرده.'
      );
    }
  };

  const headers = new Headers(options.headers);

  let response = await doFetch({ ...options, headers });
  let payload = await parseJson(response);

  if (response.status === 401) {
    const hadAuth = headers.has('Authorization');
    if (hadAuth) {
      try {
        const newAccess = await refreshAccessToken();
        headers.set('Authorization', `Bearer ${newAccess}`);
        response = await doFetch({ ...options, headers });
        payload = await parseJson(response);
      } catch {
        // refreshAccessToken already handled redirect/storage.
      }
    }
  }

  if (!response.ok) {
    const message = extractErrorMessage(payload, response.statusText);
    if (response.status === 401 && typeof message === 'string' && message.includes('token')) {
      clearAuthStorage();
      navigateToLogin();
    }
    throw new Error(message);
  }

  return payload as T;
}

type CourseChatHistoryItem = {
  id: number;
  role: 'user' | 'assistant' | 'system';
  type: 'text' | 'widget';
  content: string;
  payload?: any;
  suggestions?: string[];
  lesson_id?: string;
  created_at: string;
};

type CourseChatHistoryResponse = {
  items: CourseChatHistoryItem[];
};

type MeApiResponse = {
  id: number;
  username: string;
  first_name?: string;
  last_name?: string;
  email: string;
  phone?: string | null;
  avatar?: string | null;
  role: string;
  is_profile_completed: boolean;
  join_date?: string;
  bio?: string | null;
  grade?: string | null;
  major?: string | null;
  is_verified?: boolean;
};

function mapMeToUserProfile(me: MeApiResponse): UserProfile {
  const first = String(me.first_name ?? '').trim();
  const last = String(me.last_name ?? '').trim();
  const name = `${first} ${last}`.trim() || me.username;
  const role = String(me.role || '').toLowerCase() as any;
  const joinDate = me.join_date ? String(me.join_date) : '';

  const avatarRaw = String(me.avatar ?? '');
  let avatar = avatarRaw;
  if (avatarRaw && !avatarRaw.startsWith('http') && !avatarRaw.startsWith('data:')) {
    avatar = `${BASE_URL}${avatarRaw.startsWith('/') ? '' : '/'}${avatarRaw}`;
  }

  return {
    id: String(me.id),
    username: me.username,
    name,
    email: me.email,
    phone: String(me.phone ?? ''),
    avatar,
    role: role === 'student' || role === 'teacher' || role === 'admin' ? role : 'student',
    grade: me.grade ?? undefined,
    major: me.major ?? undefined,
    bio: me.bio ?? undefined,
    joinDate,
    isVerified: Boolean(me.is_verified ?? me.is_profile_completed),
  };
}

/**
 * Dashboard Service
 * Handles all data fetching for the student dashboard.
 * Currently returns mock data, but ready to be replaced with API calls.
 */
export const DashboardService = {
  getStats: async () => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const courses = await DashboardService.getCourses();
    const totalCourses = courses.length;
    const activeCourses = totalCourses;
    const completionPercent = totalCourses
      ? Math.round(courses.reduce((acc, c) => acc + (Number(c.progress) || 0), 0) / totalCourses)
      : 0;

    return {
      activeCourses,
      totalCourses,
      completionPercent,
      averageScore: 0,
      studyHours: '0',
      studyMinutes: '0',
    };
  },

  getActivities: async () => {
    return [];
  },

  getUpcomingEvents: async () => {
    return [];
  },

  getStudentProfile: async () => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const url = `${API_URL}/accounts/me/`;
    const me = await requestJson<MeApiResponse>(url, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
    });
    return mapMeToUserProfile(me);
  },

  getCourses: async (): Promise<Course[]> => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const url = `${API_URL}/classes/student/courses/`;
    return requestJson<Course[]>(url, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
    });
  },

  getExams: async () => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    // Fetch real exam prep data from API
    const url = `${API_URL}/classes/student/exam-preps/`;
    const data = await requestJson<{
      id: number;
      title: string;
      description: string;
      tags: string[];
      questions: number;
      createdAt?: string;
      instructor?: string;
    }[]>(url, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
    });
    // Transform to Exam type expected by frontend
    return data.map(item => ({
      id: item.id,
      title: item.title,
      description: item.description,
      tags: item.tags || [],
      questions: item.questions,
    }));
  },

  getExam: async (examId: string) => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    // Try to fetch real exam prep detail from API
    const url = `${API_URL}/classes/student/exam-preps/${examId}/`;
    const data = await requestJson<{
      id: number;
      title: string;
      description: string;
      questions: {
        question_id: string;
        question_text_markdown: string;
        options: { label: string; text_markdown: string }[];
      }[];
      totalQuestions: number;
      subject?: string;
    }>(url, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
    });

    // Transform to Exam type expected by frontend
    const questionsList = data.questions.map((q, idx) => ({
      id: q.question_id,
      number: idx + 1,
      text: q.question_text_markdown,
      options: q.options.map((opt, optIdx) => ({
        id: String(opt.label || optIdx),
        label: opt.label,
        text: opt.text_markdown,
      })),
    }));

    return {
      id: data.id,
      title: data.title,
      description: data.description,
      tags: [],
      questions: data.totalQuestions,
      subject: data.subject || data.title,
      totalQuestions: data.totalQuestions,
      currentQuestionIndex: 0,
      questionsList,
    };
  },

  submitExamPrep: async (examId: string, payload: { answers: Record<string, string>; finalize?: boolean }) => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const url = `${API_URL}/classes/student/exam-preps/${examId}/submit/`;
    return requestJson<{
      score_0_100: number;
      correct_count: number;
      total_questions: number;
      finalized: boolean;
    }>(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
  },

  getExamPrepResult: async (examId: string) => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const url = `${API_URL}/classes/student/exam-preps/${examId}/result/`;
    return requestJson<{
      finalized: boolean;
      score_0_100: number;
      correct_count: number;
      total_questions: number;
      answers: Record<string, string>;
      items: { question_id: string; selected_label: string; is_correct: boolean }[];
    }>(url, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
    });
  },

  resetExamPrepAttempt: async (examId: string) => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const url = `${API_URL}/classes/student/exam-preps/${examId}/reset/`;
    return requestJson<{
      finalized: boolean;
      score_0_100: number;
      correct_count: number;
      total_questions: number;
    }>(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
    });
  },

  getTickets: async () => {
    await new Promise(resolve => setTimeout(resolve, 600));
    return MOCK_TICKETS;
  },

  getNotifications: async (): Promise<Notification[]> => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const url = `${API_URL}/classes/student/notifications/`;
    const response = await requestJson<Notification[]>(url, {
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
    });
    return response || [];
  },

  markNotificationRead: async (id: string) => {
    if (!RAW_API_URL) return;
    const url = `${API_URL}/notifications/${encodeURIComponent(id)}/read/`;
    await fetch(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
    });
  },

  markAllNotificationsRead: async () => {
    if (!RAW_API_URL) return;
    const url = `${API_URL}/notifications/read-all/`;
    await fetch(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
    });
  },

  getCalendarEvents: async () => {
    await new Promise(resolve => setTimeout(resolve, 500));
    return MOCK_CALENDAR_EVENTS;
  },

  getCourseContent: async (courseId?: string): Promise<CourseContent> => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const id = String(courseId ?? '').trim();
    if (!id) {
      throw new Error('شناسه کلاس مشخص نیست.');
    }

    const url = `${API_URL}/classes/student/courses/${encodeURIComponent(id)}/content/`;
    return requestJson<CourseContent>(url, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
    });
  },

  downloadCoursePdf: async (courseId?: string): Promise<Blob> => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const id = String(courseId ?? '').trim();
    if (!id) {
      throw new Error('شناسه کلاس مشخص نیست.');
    }

    const url = `${API_URL}/classes/student/courses/${encodeURIComponent(id)}/export-pdf/`;
    return requestBlob(url, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
    });
  },

  sendCourseChatMessage: async (
    courseId: string,
    payload: { message: string; lesson_id?: string | null; page_context?: string; page_material?: string; student_name?: string }
  ) => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const cid = String(courseId ?? '').trim();
    if (!cid) {
      throw new Error('شناسه کلاس مشخص نیست.');
    }

    const url = `${API_URL}/classes/student/courses/${encodeURIComponent(cid)}/chat/`;
    return requestJson<any>(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
  },

  sendCourseChatMedia: async (
    courseId: string,
    formData: FormData
  ) => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const cid = String(courseId ?? '').trim();
    if (!cid) {
      throw new Error('شناسه کلاس مشخص نیست.');
    }

    const url = `${API_URL}/classes/student/courses/${encodeURIComponent(cid)}/chat-media/`;
    return requestFormData<any>(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
      body: formData,
    });
  },

  getCourseChatHistory: async (courseId: string, lessonId?: string | null): Promise<CourseChatHistoryResponse> => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const cid = String(courseId ?? '').trim();
    if (!cid) {
      throw new Error('شناسه کلاس مشخص نیست.');
    }

    const lid = String(lessonId ?? '').trim();
    const qs = lid ? `?lesson_id=${encodeURIComponent(lid)}` : '';
    const url = `${API_URL}/classes/student/courses/${encodeURIComponent(cid)}/chat-history/${qs}`;
    return requestJson<CourseChatHistoryResponse>(url, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
    });
  },

  sendExamPrepChatMessage: async (
    examId: string,
    payload: { message: string; question_id?: string | null; student_selected?: string; is_checked?: boolean }
  ) => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const eid = String(examId ?? '').trim();
    if (!eid) {
      throw new Error('شناسه آزمون مشخص نیست.');
    }

    const url = `${API_URL}/classes/student/exam-preps/${encodeURIComponent(eid)}/chat/`;
    return requestJson<any>(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
  },

  sendExamPrepChatMedia: async (examId: string, formData: FormData) => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const eid = String(examId ?? '').trim();
    if (!eid) {
      throw new Error('شناسه آزمون مشخص نیست.');
    }

    const url = `${API_URL}/classes/student/exam-preps/${encodeURIComponent(eid)}/chat-media/`;
    return requestFormData<any>(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
      body: formData,
    });
  },

  getExamPrepChatHistory: async (examId: string, questionId?: string | null): Promise<CourseChatHistoryResponse> => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const eid = String(examId ?? '').trim();
    if (!eid) {
      throw new Error('شناسه آزمون مشخص نیست.');
    }

    const qid = String(questionId ?? '').trim();
    const qs = qid ? `?question_id=${encodeURIComponent(qid)}` : '';
    const url = `${API_URL}/classes/student/exam-preps/${encodeURIComponent(eid)}/chat-history/${qs}`;
    return requestJson<CourseChatHistoryResponse>(url, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
    });
  },

  getChapterQuiz: async (courseId: string, chapterId: string) => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const cid = String(courseId ?? '').trim();
    const ch = String(chapterId ?? '').trim();
    if (!cid || !ch) {
      throw new Error('شناسه کلاس/فصل مشخص نیست.');
    }
    const url = `${API_URL}/classes/student/courses/${encodeURIComponent(cid)}/chapters/${encodeURIComponent(ch)}/quiz/`;
    return requestJson<any>(url, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
    });
  },

  submitChapterQuiz: async (courseId: string, chapterId: string, answers: Record<string, string>) => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const cid = String(courseId ?? '').trim();
    const ch = String(chapterId ?? '').trim();
    if (!cid || !ch) {
      throw new Error('شناسه کلاس/فصل مشخص نیست.');
    }
    const url = `${API_URL}/classes/student/courses/${encodeURIComponent(cid)}/chapters/${encodeURIComponent(ch)}/quiz/`;
    return requestJson<any>(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ answers }),
    });
  },

  getFinalExam: async (courseId: string) => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const cid = String(courseId ?? '').trim();
    if (!cid) {
      throw new Error('شناسه کلاس مشخص نیست.');
    }
    const url = `${API_URL}/classes/student/courses/${encodeURIComponent(cid)}/final-exam/`;
    return requestJson<any>(url, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
    });
  },

  submitFinalExam: async (courseId: string, answers: Record<string, string>) => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const cid = String(courseId ?? '').trim();
    if (!cid) {
      throw new Error('شناسه کلاس مشخص نیست.');
    }
    const url = `${API_URL}/classes/student/courses/${encodeURIComponent(cid)}/final-exam/`;
    return requestJson<any>(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ answers }),
    });
  },

  getUserProfile: async () => {
    return DashboardService.getStudentProfile();
  },

  updateUserProfile: async (data: Partial<UserProfile>) => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const url = `${API_URL}/accounts/me/`;

    // Allow passing either MeUpdate fields or UserProfile-ish fields.
    const payload: any = {};
    if ((data as any).first_name !== undefined) payload.first_name = (data as any).first_name;
    if ((data as any).last_name !== undefined) payload.last_name = (data as any).last_name;
    if (data.email !== undefined) payload.email = data.email;
    if (data.bio !== undefined) payload.bio = data.bio;
    if (data.grade !== undefined) payload.grade = data.grade;
    if (data.major !== undefined) payload.major = data.major;
    if ((data as any).avatar !== undefined) payload.avatar = (data as any).avatar;

    const me = await requestJson<MeApiResponse>(url, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    // Keep auth header dropdown in sync.
    persistUser(me as any);
    return mapMeToUserProfile(me);
  }
};
