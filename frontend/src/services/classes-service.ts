export type Step1TranscribeResponse = {
  id: number;
  status: 'transcribing' | 'transcribed' | 'failed' | 'structuring' | 'structured' | 'prereq_extracting' | 'prereq_extracted' | 'prereq_teaching' | 'prereq_taught' | 'recapping' | 'recapped';
  title: string;
  description: string;
  source_mime_type: string;
  source_original_name: string;
  transcript_markdown: string;
  created_at: string;
};

export type Step2StructureResponse = {
  id: number;
  status:
    | 'structuring'
    | 'structured'
    | 'failed'
    | 'transcribed'
    | 'transcribing'
    | 'prereq_extracting'
    | 'prereq_extracted'
    | 'prereq_teaching'
    | 'prereq_taught'
    | 'recapping'
    | 'recapped';
  title: string;
  description: string;
  structure_json: string;
  created_at: string;
};
export type ClassCreationSessionDetail = {
  id: number;
  status: string;
  title: string;
  description: string;
  level?: string;
  duration?: string;
  source_mime_type: string;
  source_original_name: string;
  transcript_markdown: string;
  structure_json: string;
  recap_markdown?: string;
  error_detail: string;
  is_published?: boolean;
  published_at?: string | null;
  invites_count?: number;
  created_at: string;
  updated_at: string;
};

export type ClassInvite = {
  id: number;
  phone: string;
  invite_code: string;
  created_at: string;
};

export type AnnouncementPriority = 'low' | 'medium' | 'high';

export type ClassAnnouncement = {
  id: number;
  title: string;
  content: string;
  priority: AnnouncementPriority;
  created_at: string;
  updated_at: string;
};

export type ClassPrerequisite = {
  id: number;
  order: number;
  name: string;
  teaching_text: string;
};

const RAW_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');

// We want all requests to target the Django API root: `${BACKEND}/api`.
// Allow either:
// - NEXT_PUBLIC_API_URL="https://example.com"  -> https://example.com/api
// - NEXT_PUBLIC_API_URL="https://example.com/api" -> https://example.com/api
const API_URL = RAW_API_URL.endsWith('/api') ? RAW_API_URL : `${RAW_API_URL}/api`;

import { refreshAccessToken } from '@/services/auth-service';

async function parseJson(response: Response) {
  const text = await response.text();
  if (!text) return null;

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
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

  let response = await doFetch(options);
  let payload = await parseJson(response);

  // Auto-refresh on 401 if we had an Authorization header
  const headers = new Headers(options.headers);
  if (response.status === 401 && headers.has('Authorization')) {
    try {
      const newAccess = await refreshAccessToken();
      headers.set('Authorization', `Bearer ${newAccess}`);
      response = await doFetch({ ...options, headers });
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
export async function getClassCreationSessionDetail(sessionId: number): Promise<ClassCreationSessionDetail> {
  const url = `${API_URL}/classes/creation-sessions/${sessionId}/`;

  return requestJson<ClassCreationSessionDetail>(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });
}

export async function updateClassCreationSession(
  sessionId: number,
  data: { title?: string; description?: string; level?: string; duration?: string; structure_json?: string | object | null }
): Promise<ClassCreationSessionDetail> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }

  const url = `${API_URL}/classes/creation-sessions/${sessionId}/`;
  return requestJson<ClassCreationSessionDetail>(url, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
}

export async function publishClassCreationSession(sessionId: number): Promise<ClassCreationSessionDetail> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }

  const url = `${API_URL}/classes/creation-sessions/${sessionId}/publish/`;
  return requestJson<ClassCreationSessionDetail>(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });
}

export async function listClassInvites(sessionId: number): Promise<ClassInvite[]> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/creation-sessions/${sessionId}/invites/`;
  return requestJson<ClassInvite[]>(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });
}

export async function addClassInvites(sessionId: number, phones: string[]): Promise<ClassInvite[]> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/creation-sessions/${sessionId}/invites/`;
  return requestJson<ClassInvite[]>(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ phones }),
  });
}

export async function deleteClassInvite(sessionId: number, inviteId: number): Promise<void> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/creation-sessions/${sessionId}/invites/${inviteId}/`;
  await requestJson<void>(url, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });
}

// ==========================================================================
// EXAM PREP INVITES
// ==========================================================================

export async function listExamPrepInvites(sessionId: number): Promise<ClassInvite[]> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/exam-prep-sessions/${sessionId}/invites/`;
  return requestJson<ClassInvite[]>(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });
}

export async function addExamPrepInvites(sessionId: number, phones: string[]): Promise<ClassInvite[]> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/exam-prep-sessions/${sessionId}/invites/`;
  return requestJson<ClassInvite[]>(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ phones }),
  });
}

export async function deleteExamPrepInvite(sessionId: number, inviteId: number): Promise<void> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/exam-prep-sessions/${sessionId}/invites/${inviteId}/`;
  await requestJson<void>(url, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });
}

export async function listClassAnnouncements(sessionId: number): Promise<ClassAnnouncement[]> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/creation-sessions/${sessionId}/announcements/`;
  return requestJson<ClassAnnouncement[]>(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });
}

export async function createClassAnnouncement(sessionId: number, payload: {
  title: string;
  content: string;
  priority: AnnouncementPriority;
}): Promise<ClassAnnouncement> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/creation-sessions/${sessionId}/announcements/`;
  return requestJson<ClassAnnouncement>(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

export async function updateClassAnnouncement(sessionId: number, announcementId: number, payload: Partial<{
  title: string;
  content: string;
  priority: AnnouncementPriority;
}>): Promise<ClassAnnouncement> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/creation-sessions/${sessionId}/announcements/${announcementId}/`;
  return requestJson<ClassAnnouncement>(url, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

export async function deleteClassAnnouncement(sessionId: number, announcementId: number): Promise<void> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/creation-sessions/${sessionId}/announcements/${announcementId}/`;
  await requestJson<void>(url, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });
}

export async function listExamPrepAnnouncements(sessionId: number): Promise<ClassAnnouncement[]> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/exam-prep-sessions/${sessionId}/announcements/`;
  return requestJson<ClassAnnouncement[]>(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });
}

export async function createExamPrepAnnouncement(sessionId: number, payload: {
  title: string;
  content: string;
  priority: AnnouncementPriority;
}): Promise<ClassAnnouncement> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/exam-prep-sessions/${sessionId}/announcements/`;
  return requestJson<ClassAnnouncement>(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

export async function updateExamPrepAnnouncement(sessionId: number, announcementId: number, payload: Partial<{
  title: string;
  content: string;
  priority: AnnouncementPriority;
}>): Promise<ClassAnnouncement> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/exam-prep-sessions/${sessionId}/announcements/${announcementId}/`;
  return requestJson<ClassAnnouncement>(url, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

export async function deleteExamPrepAnnouncement(sessionId: number, announcementId: number): Promise<void> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/exam-prep-sessions/${sessionId}/announcements/${announcementId}/`;
  await requestJson<void>(url, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });
}

export async function listClassPrerequisites(sessionId: number): Promise<ClassPrerequisite[]> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/creation-sessions/${sessionId}/prerequisites/`;
  return requestJson<ClassPrerequisite[]>(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });
}

export async function runStep3Prerequisites(sessionId: number): Promise<void> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/creation-sessions/step-3/`;
  await requestJson(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export async function runStep4PrerequisiteTeaching(sessionId: number): Promise<void> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
  const url = `${API_URL}/classes/creation-sessions/step-4/`;
  await requestJson(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ session_id: sessionId }),
  });
}

function extractErrorMessage(payload: unknown, fallback: string) {
  if (payload && typeof payload === 'object') {
    const obj = payload as Record<string, unknown>;

    // Our API sometimes returns: { detail: "Validation error.", errors: { field: [..] } }
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

    if (typeof obj.detail === 'string') return obj.detail;
    if (typeof obj.message === 'string') return obj.message;

    const entries = Object.entries(obj)
      .map(([key, value]) => {
        if (typeof value === 'string') return `${key}: ${value}`;
        if (Array.isArray(value)) {
          const joined = value
            .map((v) => (typeof v === 'string' ? v : JSON.stringify(v)))
            .filter(Boolean)
            .join(', ');
          return joined ? `${key}: ${joined}` : null;
        }
        if (value && typeof value === 'object') return `${key}: ${JSON.stringify(value)}`;
        return null;
      })
      .filter((x): x is string => Boolean(x));

    if (entries.length) return entries.join(' | ');
  }
  if (Array.isArray(payload)) {
    return payload.map((item) => String(item)).join(', ');
  }
  if (typeof payload === 'string' && payload.trim()) return payload;
  return fallback;
}

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

export async function transcribeClassCreationStep1(params: {
  title: string;
  description?: string;
  file: File;
  clientRequestId?: string;
  runFullPipeline?: boolean;
}): Promise<Step1TranscribeResponse> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }

  const formData = new FormData();
  formData.append('title', params.title);
  formData.append('description', params.description ?? '');
  formData.append('file', params.file, params.file.name);
  if (params.clientRequestId) {
    formData.append('client_request_id', params.clientRequestId);
  }
  if (params.runFullPipeline) {
    formData.append('run_full_pipeline', 'true');
  }

  const url = `${API_URL}/classes/creation-sessions/step-1/`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
      body: formData,
    });
  } catch (error) {
    throw new Error(
      `ارتباط با سرور برقرار نشد. (آدرس فعلی API: ${RAW_API_URL})` +
        ' معمولاً یکی از این‌هاست: بک‌اند اجرا نیست، آدرس/پورت اشتباه است، یا مرورگر به خاطر CORS/Mixed Content درخواست را بلاک کرده.'
    );
  }

  const payload = await parseJson(response);

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, response.statusText));
  }

  return payload as Step1TranscribeResponse;
}

export async function structureClassCreationStep2(params: {
  sessionId: number;
}): Promise<Step2StructureResponse> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }

  const url = `${API_URL}/classes/creation-sessions/step-2/`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ session_id: params.sessionId }),
    });
  } catch {
    throw new Error(
      `ارتباط با سرور برقرار نشد. (آدرس فعلی API: ${RAW_API_URL})` +
        ' معمولاً یکی از این‌هاست: بک‌اند اجرا نیست، آدرس/پورت اشتباه است، یا مرورگر به خاطر CORS/Mixed Content درخواست را بلاک کرده.'
    );
  }

  const payload = await parseJson(response);
  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, response.statusText));
  }

  return payload as Step2StructureResponse;
}


// ==========================================================================
// EXAM PREP PIPELINE (2 Steps)
// ==========================================================================

export type ExamPrepStatus =
  | 'exam_transcribing'
  | 'exam_transcribed'
  | 'exam_structuring'
  | 'exam_structured'
  | 'failed';

export interface ExamPrepStep1Response {
  id: number;
  status: ExamPrepStatus;
  pipeline_type: 'exam_prep';
  title: string;
  description: string;
  source_mime_type: string;
  source_original_name: string;
  transcript_markdown: string;
  created_at: string;
}

export interface ExamPrepSessionDetail {
  id: number;
  status: ExamPrepStatus;
  pipeline_type: 'exam_prep';
  title: string;
  description: string;
  level: string;
  duration: string;
  transcript_markdown: string;
  exam_prep_json: string;
  exam_prep_data: ExamPrepData | null;
  invites_count?: number;
  is_published: boolean;
  published_at: string | null;
  error_detail: string;
  created_at: string;
  updated_at: string;
}

export interface ExamPrepData {
  exam_prep: {
    title: string;
    source_transcript_id?: string;
    questions: ExamPrepQuestion[];
  };
}

export interface ExamPrepQuestion {
  question_id: string;
  question_text_markdown: string;
  options: { label: string; text_markdown: string }[];
  correct_option_label: string | null;
  correct_option_text_markdown: string | null;
  teacher_solution_markdown: string;
  final_answer_markdown: string;
  confidence: number;
  issues?: string[];
}

/**
 * Exam Prep Step 1: Upload and transcribe audio/video.
 */
export async function transcribeExamPrepStep1(params: {
  title: string;
  description?: string;
  file: File;
  clientRequestId?: string;
  runFullPipeline?: boolean;
}): Promise<ExamPrepStep1Response> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }

  const formData = new FormData();
  formData.append('title', params.title);
  formData.append('description', params.description ?? '');
  formData.append('file', params.file, params.file.name);
  if (params.clientRequestId) {
    formData.append('client_request_id', params.clientRequestId);
  }
  if (params.runFullPipeline) {
    formData.append('run_full_pipeline', 'true');
  }

  const url = `${API_URL}/classes/exam-prep-sessions/step-1/`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAccessToken()}`,
      },
      body: formData,
    });
  } catch {
    throw new Error(
      `ارتباط با سرور برقرار نشد. (آدرس فعلی API: ${RAW_API_URL})` +
        ' معمولاً یکی از این‌هاست: بک‌اند اجرا نیست، آدرس/پورت اشتباه است، یا مرورگر به خاطر CORS/Mixed Content درخواست را بلاک کرده.'
    );
  }

  const payload = await parseJson(response);
  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, response.statusText));
  }

  return payload as ExamPrepStep1Response;
}

/**
 * Fetch exam prep session detail (for polling).
 */
export async function fetchExamPrepSession(sessionId: number): Promise<ExamPrepSessionDetail> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }

  const url = `${API_URL}/classes/exam-prep-sessions/${sessionId}/`;
  const payload = await requestJson(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });

  return payload as ExamPrepSessionDetail;
}

/**
 * Publish an exam prep session.
 */
export async function publishExamPrepSession(sessionId: number): Promise<ExamPrepSessionDetail> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }

  const url = `${API_URL}/classes/exam-prep-sessions/${sessionId}/publish/`;
  const payload = await requestJson(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });

  return payload as ExamPrepSessionDetail;
}

/**
 * List all exam prep sessions for the teacher.
 */
export async function listExamPrepSessions(): Promise<ExamPrepSessionDetail[]> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }

  const url = `${API_URL}/classes/exam-prep-sessions/`;
  const payload = await requestJson(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });

  return payload as ExamPrepSessionDetail[];
}

/**
 * Update an exam prep session.
 */
export async function updateExamPrepSession(
  sessionId: number,
  data: Partial<{
    title: string;
    description: string;
    level: string;
    duration: string;
    exam_prep_json: any;
  }>,
): Promise<ExamPrepSessionDetail> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }

  const url = `${API_URL}/classes/exam-prep-sessions/${sessionId}/`;
  const payload = await requestJson(url, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  return payload as ExamPrepSessionDetail;
}

/**
 * Delete an exam prep session.
 */
export async function deleteExamPrepSession(sessionId: number): Promise<void> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }

  const url = `${API_URL}/classes/exam-prep-sessions/${sessionId}/`;
  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${getAccessToken()}`,
    },
  });

  if (!response.ok) {
    const payload = await parseJson(response);
    throw new Error(extractErrorMessage(payload, response.statusText));
  }
}
