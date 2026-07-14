import type {
  CalendarEvent,
  Course,
  CourseContent,
  DashboardEvent,
  Notification,
  Ticket,
  UserProfile,
} from '@/types';
import { clearAuthStorage, getStoredTokens, persistTokens, persistUser, refreshAccessToken } from '@/services/auth-service';
import {
  getStudentCalendar,
  listStudentExercises,
  type CalendarEventDto,
  type StudentExerciseListItem,
} from '@/services/exercises-service';
import { PERSIAN_MONTHS } from '@/constants/calendar';
import { getStudentExerciseAction } from '@/lib/exercise-actions';

const RAW_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');
const API_URL = RAW_API_URL.endsWith('/api') ? RAW_API_URL : `${RAW_API_URL}/api`;
const BASE_URL = RAW_API_URL.replace(/\/api$/, '');

type CalendarExerciseLookup = Map<string, StudentExerciseListItem>;

function calendarExerciseKey(sessionId: number, exerciseId: number): string {
  return `${sessionId}:${exerciseId}`;
}

async function loadCalendarExerciseLookup(
  dtos: CalendarEventDto[]
): Promise<CalendarExerciseLookup> {
  const sessionIds = Array.from(
    new Set(
      dtos
        .filter((dto) => dto.kind === 'exercise_deadline' && dto.exerciseId)
        .map((dto) => dto.sessionId)
        .filter((sessionId) => Number.isFinite(sessionId))
    )
  );

  const perSession = await Promise.all(
    sessionIds.map(async (sessionId) => {
      const exercises = await listStudentExercises(sessionId).catch(
        () => [] as StudentExerciseListItem[]
      );
      return [sessionId, exercises] as const;
    })
  );

  const lookup: CalendarExerciseLookup = new Map();
  perSession.forEach(([sessionId, exercises]) => {
    exercises.forEach((exercise) => {
      lookup.set(calendarExerciseKey(sessionId, exercise.id), exercise);
    });
  });
  return lookup;
}

function findCalendarExercise(
  dto: CalendarEventDto,
  lookup?: CalendarExerciseLookup
): StudentExerciseListItem | undefined {
  if (dto.kind !== 'exercise_deadline' || !dto.exerciseId) return undefined;
  return lookup?.get(calendarExerciseKey(dto.sessionId, dto.exerciseId));
}

/**
 * Convert a backend calendar DTO (Tehran-tz ISO datetime, see E9) into the UI
 * `CalendarEvent` shape the Jalali calendar engine expects: a zero-padded Jalali
 * `YYYY-MM-DD` date + `HH:MM` time, both computed in `Asia/Tehran` so the day
 * never drifts across the browser's timezone. Returns null for undated events.
 */
function toCalendarEvent(
  dto: CalendarEventDto,
  exercise?: StudentExerciseListItem
): CalendarEvent | null {
  if (!dto.datetime) return null;
  const when = new Date(dto.datetime);
  if (Number.isNaN(when.getTime())) return null;

  const dateParts = new Intl.DateTimeFormat('en-US', {
    calendar: 'persian',
    timeZone: 'Asia/Tehran',
    numberingSystem: 'latn',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(when);
  const timeParts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Tehran',
    numberingSystem: 'latn',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(when);
  const part = (parts: Intl.DateTimeFormatPart[], type: Intl.DateTimeFormatPartTypes) =>
    parts.find((p) => p.type === type)?.value ?? '';

  const year = part(dateParts, 'year');
  const month = part(dateParts, 'month');
  const day = part(dateParts, 'day');
  let hour = part(timeParts, 'hour');
  if (hour === '24') hour = '00'; // some engines emit "24" for midnight
  const minute = part(timeParts, 'minute');

  const isExam = dto.kind === 'exam_prep';
  const exerciseAction = exercise ? getStudentExerciseAction(exercise, dto.sessionId) : null;
  const fallbackExerciseHref =
    dto.kind === 'exercise_deadline' && dto.exerciseId
      ? dto.isCompleted
        ? `/exercises/${dto.exerciseId}/result?session=${dto.sessionId}`
        : `/exercises/${dto.exerciseId}?session=${dto.sessionId}`
      : undefined;
  const href =
    exerciseAction?.href ??
    fallbackExerciseHref ??
    (isExam ? `/exam/${dto.sessionId}` : undefined);
  const actionLabel =
    exerciseAction?.label ??
    (isExam ? 'باز کردن' : dto.isCompleted ? 'دیدن نتیجه' : 'شروع تمرین');
  const isCompleted =
    dto.isCompleted ||
    Boolean(exercise?.submissionStatus && exercise.submissionStatus !== 'draft');
  const assignmentPriority =
    exerciseAction?.kind === 'continue'
      ? 'high'
      : exerciseAction?.kind === 'start'
        ? 'medium'
        : 'low';

  return {
    id: dto.id,
    title: dto.title,
    description: isExam ? 'جلسه آمادگی آزمون' : `مهلت ارسال تمرین · ${actionLabel}`,
    datetime: dto.datetime,
    subject: dto.courseTitle,
    date: `${year}-${month}-${day}`,
    time: `${hour}:${minute}`,
    type: isExam ? 'exam' : 'assignment',
    priority: isExam ? (isCompleted ? 'low' : 'high') : assignmentPriority,
    isCompleted,
    kind: dto.kind,
    sessionId: dto.sessionId,
    exerciseId: dto.exerciseId,
    href,
    actionLabel,
  };
}

function toDashboardEvent(event: CalendarEvent): DashboardEvent {
  const [, rawMonth, rawDay] = event.date.split('-');
  const monthIndex = Math.max(0, Number(rawMonth) - 1);
  const label =
    event.type === 'assignment'
      ? event.actionLabel ?? (event.isCompleted ? 'تمرین تکمیل شده' : 'مهلت تمرین')
      : event.isCompleted
        ? 'آمادگی آزمون تکمیل شده'
        : 'زمان آمادگی آزمون';

  return {
    id: event.id,
    title: event.title,
    status: event.time ? `${label} · ${event.time}` : label,
    date: rawDay ?? '',
    month: PERSIAN_MONTHS[monthIndex] ?? '',
    icon: event.type === 'assignment' ? 'file' : 'clock',
    href: event.href,
  };
}

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

  getUpcomingEvents: async (): Promise<DashboardEvent[]> => {
    if (!RAW_API_URL) return [];
    const events = await DashboardService.getCalendarEvents();
    const today = new Intl.DateTimeFormat('en-US', {
      calendar: 'persian',
      timeZone: 'Asia/Tehran',
      numberingSystem: 'latn',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    })
      .formatToParts(new Date())
      .reduce((acc, part) => {
        if (part.type === 'year' || part.type === 'month' || part.type === 'day') {
          acc[part.type] = part.value;
        }
        return acc;
      }, {} as Record<'year' | 'month' | 'day', string>);
    const todayKey = `${today.year}-${today.month}-${today.day}`;
    const now = Date.now();
    return events
      .filter((event) => {
        if (event.datetime) {
          const eventTime = Date.parse(event.datetime);
          return Number.isNaN(eventTime) ? event.date >= todayKey : eventTime > now;
        }
        return event.date >= todayKey;
      })
      .sort((a, b) => {
        const aTime = a.datetime ? Date.parse(a.datetime) : Number.NaN;
        const bTime = b.datetime ? Date.parse(b.datetime) : Number.NaN;
        if (!Number.isNaN(aTime) && !Number.isNaN(bTime)) return aTime - bTime;
        return `${a.date} ${a.time ?? ''}`.localeCompare(`${b.date} ${b.time ?? ''}`);
      })
      .slice(0, 5)
      .map(toDashboardEvent);
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
      sourceType?: 'media' | 'pdf';
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
      sourceType: item.sourceType,
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
        type?: string;
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
      type: (q.type as 'multiple_choice' | 'true_false' | 'fill_blank' | 'short_answer') || undefined,
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

  checkExamPrepAnswer: async (examId: string, questionId: string, answer: string) => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const url = `${API_URL}/classes/student/exam-preps/${examId}/check-answer/`;
    return requestJson<{
      is_correct: boolean;
      attempts: number;
      hint: string;
      encouragement: string;
      score_for_question: number;
    }>(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ question_id: questionId, answer }),
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
      items: { question_id: string; selected_label: string; is_correct: boolean; attempts: number; score_for_question: number }[];
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

  getTickets: async (): Promise<Ticket[]> => {
    const url = `${API_URL}/admin/my-tickets/`;
    const response = await requestJson<Ticket[]>(url, {
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
    });
    return response || [];
  },

  createTicket: async (data: {
    subject: string;
    department: string;
    content: string;
    priority?: string;
  }): Promise<{ id: string; subject: string; status: string }> => {
    const url = `${API_URL}/admin/my-tickets/create/`;
    return requestJson(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        subject: data.subject,
        department: data.department,
        content: data.content,
        priority: data.priority ?? 'medium',
      }),
    });
  },

  replyToTicket: async (
    ticketPk: number,
    content: string,
  ): Promise<{ id: string; content: string; isAdmin: boolean; createdAt: string }> => {
    const url = `${API_URL}/admin/my-tickets/${ticketPk}/reply/`;
    return requestJson(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ content }),
    });
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

  getCalendarEvents: async (): Promise<CalendarEvent[]> => {
    if (!RAW_API_URL) return [];
    const dtos = await getStudentCalendar();
    const exerciseLookup = await loadCalendarExerciseLookup(dtos);
    return dtos
      .map((dto) => toCalendarEvent(dto, findCalendarExercise(dto, exerciseLookup)))
      .filter((event): event is CalendarEvent => event !== null);
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

  // Build a NEW quiz targeting the student's weak points (only after a fail).
  // Returns the new quiz in the same shape as getChapterQuiz.
  regenerateChapterQuiz: async (courseId: string, chapterId: string) => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const cid = String(courseId ?? '').trim();
    const ch = String(chapterId ?? '').trim();
    if (!cid || !ch) {
      throw new Error('شناسه کلاس/فصل مشخص نیست.');
    }
    const url = `${API_URL}/classes/student/courses/${encodeURIComponent(cid)}/chapters/${encodeURIComponent(ch)}/quiz/regenerate/`;
    return requestJson<any>(url, {
      method: 'POST',
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

  // Build a NEW final exam targeting the student's weak points (only after a fail).
  regenerateFinalExam: async (courseId: string) => {
    if (!RAW_API_URL) {
      throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
    }
    const cid = String(courseId ?? '').trim();
    if (!cid) {
      throw new Error('شناسه کلاس مشخص نیست.');
    }
    const url = `${API_URL}/classes/student/courses/${encodeURIComponent(cid)}/final-exam/regenerate/`;
    return requestJson<any>(url, {
      method: 'POST',
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
