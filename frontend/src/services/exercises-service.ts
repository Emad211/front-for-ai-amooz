/**
 * Exercise Hub API layer (docs/features/exercise-hub.md).
 * All exercise calls go through here — never fetch ad hoc from components.
 */
import { refreshAccessToken } from '@/services/auth-service';

const RAW_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');
const API_URL = RAW_API_URL.endsWith('/api') ? RAW_API_URL : `${RAW_API_URL}/api`;

export type ExerciseStatus = 'draft' | 'extracting' | 'extracted' | 'published' | 'failed';
export type SubmissionStatus = 'draft' | 'submitted' | 'grading' | 'graded' | 'grading_failed';
export type QuestionType = 'descriptive' | 'multiple_choice' | 'fill_blank';

export type ExerciseListItem = {
  id: number;
  title: string;
  description: string;
  status: ExerciseStatus;
  deadline: string | null;
  assistantEnabled: boolean;
  allowLate: boolean;
  createdAt: string;
  updatedAt: string;
};

export type ExerciseQuestion = {
  id: number;
  order: number;
  questionMarkdown: string;
  questionType: QuestionType;
  options: unknown[];
  referenceAnswerMarkdown: string;
  maxPoints: string;
  gradingNotes: string;
};

export type ExerciseSection = {
  id: number;
  order: number;
  title: string;
  assistantEnabled: boolean;
  questions: ExerciseQuestion[];
};

export type ExerciseAsset = {
  id: number;
  kind: 'pdf' | 'image';
  order: number;
  fileUrl: string;
};

export type ExerciseDetail = ExerciseListItem & {
  sections: ExerciseSection[];
  assets: ExerciseAsset[];
};

export type SubmissionListItem = {
  id: number;
  studentId: number;
  studentName: string;
  status: SubmissionStatus;
  isLate: boolean;
  scorePoints: string | null;
  maxPoints: string | null;
  overridden: boolean;
};

export type PerQuestionResult = {
  question_id: string;
  llm_score?: number | null;
  teacher_score?: number | null;
  score_points?: number | null;
  max_points?: number | null;
  label?: string;
  feedback?: string;
  teacher_feedback?: string | null;
  missing_points?: string[];
};

export type SubmissionDetail = {
  id: number;
  studentId: number;
  studentName: string;
  status: SubmissionStatus;
  isLate: boolean;
  answers: Record<string, { text?: string; images?: string[] }>;
  result: { per_question?: PerQuestionResult[] };
  scorePoints: string | null;
  maxPoints: string | null;
  overriddenAt: string | null;
};

export type QuestionOverride = {
  question_id: string;
  teacher_score?: number;
  teacher_feedback?: string;
};

function assertApiUrl(): void {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }
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

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (payload && typeof payload === 'object') {
    const obj = payload as Record<string, unknown>;
    if (typeof obj.detail === 'string') return obj.detail;
    if (typeof obj.message === 'string') return obj.message;
  }
  if (typeof payload === 'string' && payload.trim()) return payload;
  return fallback;
}

async function parseJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function requestJson<T>(url: string, options: RequestInit): Promise<T> {
  assertApiUrl();
  const doFetch = (reqOptions: RequestInit) => fetch(url, reqOptions);

  let response = await doFetch(options);
  let payload = await parseJson(response);

  const headers = new Headers(options.headers);
  if (response.status === 401 && headers.has('Authorization')) {
    try {
      const newAccess = await refreshAccessToken();
      headers.set('Authorization', `Bearer ${newAccess}`);
      response = await doFetch({ ...options, headers });
      payload = await parseJson(response);
    } catch {
      /* refreshAccessToken handles redirect/cleanup */
    }
  }

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, response.statusText));
  }
  return payload as T;
}

function authHeaders(): HeadersInit {
  return { Authorization: `Bearer ${getAccessToken()}` };
}

function jsonHeaders(): HeadersInit {
  return { ...authHeaders(), 'Content-Type': 'application/json' };
}

/* ── Teacher endpoints ─────────────────────────────────────────────── */

export async function listExercises(sessionId: number): Promise<ExerciseListItem[]> {
  return requestJson(`${API_URL}/classes/creation-sessions/${sessionId}/exercises/`, {
    method: 'GET',
    headers: authHeaders(),
  });
}

export async function createExercise(
  sessionId: number,
  data: { title: string; description?: string; files?: File[] }
): Promise<ExerciseDetail> {
  const form = new FormData();
  form.append('title', data.title);
  if (data.description) form.append('description', data.description);
  (data.files ?? []).forEach((f) => form.append('files', f));
  // Note: no Content-Type header — the browser sets the multipart boundary.
  return requestJson(`${API_URL}/classes/creation-sessions/${sessionId}/exercises/`, {
    method: 'POST',
    headers: authHeaders(),
    body: form,
  });
}

export async function getExercise(exerciseId: number): Promise<ExerciseDetail> {
  return requestJson(`${API_URL}/classes/exercises/${exerciseId}/`, {
    method: 'GET',
    headers: authHeaders(),
  });
}

export async function updateExercise(
  exerciseId: number,
  data: { title?: string; deadline?: string | null; allow_late?: boolean; assistant_enabled?: boolean }
): Promise<ExerciseDetail> {
  return requestJson(`${API_URL}/classes/exercises/${exerciseId}/`, {
    method: 'PATCH',
    headers: jsonHeaders(),
    body: JSON.stringify(data),
  });
}

export async function deleteExercise(exerciseId: number): Promise<void> {
  await requestJson(`${API_URL}/classes/exercises/${exerciseId}/`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
}

export async function extractExercise(exerciseId: number): Promise<{ detail: string; status: string }> {
  return requestJson(`${API_URL}/classes/exercises/${exerciseId}/extract/`, {
    method: 'POST',
    headers: authHeaders(),
  });
}

export async function publishExercise(exerciseId: number): Promise<ExerciseDetail> {
  return requestJson(`${API_URL}/classes/exercises/${exerciseId}/publish/`, {
    method: 'POST',
    headers: authHeaders(),
  });
}

export async function updateSection(
  sectionId: number,
  data: { assistant_enabled?: boolean; title?: string }
): Promise<{ id: number; assistantEnabled: boolean; title: string }> {
  return requestJson(`${API_URL}/classes/exercises/sections/${sectionId}/`, {
    method: 'PATCH',
    headers: jsonHeaders(),
    body: JSON.stringify(data),
  });
}

export async function updateQuestion(
  questionId: number,
  data: {
    question_markdown?: string;
    question_type?: QuestionType;
    options?: unknown[];
    reference_answer_markdown?: string;
    max_points?: number;
  }
): Promise<{ id: number }> {
  return requestJson(`${API_URL}/classes/exercises/questions/${questionId}/`, {
    method: 'PATCH',
    headers: jsonHeaders(),
    body: JSON.stringify(data),
  });
}

export async function listSubmissions(exerciseId: number): Promise<SubmissionListItem[]> {
  return requestJson(`${API_URL}/classes/exercises/${exerciseId}/submissions/`, {
    method: 'GET',
    headers: authHeaders(),
  });
}

export async function getSubmission(submissionId: number): Promise<SubmissionDetail> {
  return requestJson(`${API_URL}/classes/exercises/submissions/${submissionId}/`, {
    method: 'GET',
    headers: authHeaders(),
  });
}

export async function overrideSubmission(
  submissionId: number,
  overrides: QuestionOverride[]
): Promise<{ id: number; scorePoints: string; result: { per_question?: PerQuestionResult[] } }> {
  return requestJson(`${API_URL}/classes/exercises/submissions/${submissionId}/override/`, {
    method: 'PATCH',
    headers: jsonHeaders(),
    body: JSON.stringify({ overrides }),
  });
}

export async function allowRedo(submissionId: number): Promise<{ status: SubmissionStatus }> {
  return requestJson(`${API_URL}/classes/exercises/submissions/${submissionId}/allow-redo/`, {
    method: 'POST',
    headers: authHeaders(),
  });
}

/* ── Student types ─────────────────────────────────────────────────── */

export type StudentExerciseListItem = {
  id: number;
  title: string;
  status: ExerciseStatus;
  deadline: string | null;
  deadlinePassed: boolean;
  allowLate: boolean;
  submissionStatus: SubmissionStatus | null;
};

// Solving-view question — NEVER carries the reference answer (server withholds it).
export type StudentQuestion = {
  id: number;
  order: number;
  questionMarkdown: string;
  questionType: QuestionType;
  options: unknown[];
  maxPoints: string;
  referenceAnswerMarkdown?: string; // present only in result/answers after reveal
};

export type StudentSection = {
  id: number;
  order: number;
  title: string;
  assistantEnabled: boolean;
  questions: StudentQuestion[];
};

export type StudentExerciseDetail = {
  id: number;
  title: string;
  description: string;
  status: ExerciseStatus;
  deadline: string | null;
  assistantEnabled: boolean;
  sections: StudentSection[];
  myAnswers: Record<string, { text?: string; images?: string[] }>;
  submissionStatus: SubmissionStatus | null;
};

export type StudentAnswers = Record<string, { text?: string; images?: string[] }>;

export type ExerciseResult = {
  status: SubmissionStatus;
  detail?: string;
  scorePoints?: string | null;
  maxPoints?: string | null;
  result?: { per_question?: PerQuestionResult[] };
  answersRevealed?: boolean;
  exercise?: {
    id: number;
    title: string;
    sections: StudentSection[];
  };
};

export type ReportCard = {
  average: number | null;
  exercises: Array<{
    exerciseId: number;
    exerciseTitle: string;
    scorePoints: string | null;
    maxPoints: string | null;
    percent: number;
  }>;
};

export type FinishedAnswer = {
  id: number;
  sessionId: number;
  courseTitle: string;
  title: string;
  sections: StudentSection[];
};

export type AssistantReply = { content: string; suggestions: string[] };

export type CalendarEventDto = {
  id: string;
  kind: 'exercise_deadline' | 'exam_prep';
  title: string;
  courseTitle: string;
  datetime: string | null;
  sessionId: number;
  exerciseId?: number;
  isCompleted: boolean;
};

/* ── Student endpoints ─────────────────────────────────────────────── */

export async function listStudentExercises(sessionId: number): Promise<StudentExerciseListItem[]> {
  return requestJson(`${API_URL}/classes/student/courses/${sessionId}/exercises/`, {
    method: 'GET',
    headers: authHeaders(),
  });
}

export async function getStudentExercise(
  sessionId: number,
  exerciseId: number
): Promise<StudentExerciseDetail> {
  return requestJson(
    `${API_URL}/classes/student/courses/${sessionId}/exercises/${exerciseId}/`,
    { method: 'GET', headers: authHeaders() }
  );
}

export async function saveExerciseDraft(
  sessionId: number,
  exerciseId: number,
  answers: StudentAnswers
): Promise<{ status: SubmissionStatus; saved: boolean }> {
  return requestJson(
    `${API_URL}/classes/student/courses/${sessionId}/exercises/${exerciseId}/draft/`,
    { method: 'PUT', headers: jsonHeaders(), body: JSON.stringify({ answers }) }
  );
}

export async function uploadAnswerImage(
  sessionId: number,
  exerciseId: number,
  questionId: number,
  file: File
): Promise<{ path: string }> {
  const form = new FormData();
  form.append('file', file);
  return requestJson(
    `${API_URL}/classes/student/courses/${sessionId}/exercises/${exerciseId}/questions/${questionId}/image/`,
    { method: 'POST', headers: authHeaders(), body: form }
  );
}

export async function submitExercise(
  sessionId: number,
  exerciseId: number,
  answers: StudentAnswers
): Promise<{ status: SubmissionStatus; isLate: boolean }> {
  return requestJson(
    `${API_URL}/classes/student/courses/${sessionId}/exercises/${exerciseId}/submit/`,
    { method: 'POST', headers: jsonHeaders(), body: JSON.stringify({ answers }) }
  );
}

export async function getExerciseResult(
  sessionId: number,
  exerciseId: number
): Promise<ExerciseResult> {
  return requestJson(
    `${API_URL}/classes/student/courses/${sessionId}/exercises/${exerciseId}/result/`,
    { method: 'GET', headers: authHeaders() }
  );
}

export async function getCourseReportCard(sessionId: number): Promise<ReportCard> {
  return requestJson(`${API_URL}/classes/student/courses/${sessionId}/report-card/`, {
    method: 'GET',
    headers: authHeaders(),
  });
}

export async function getOverallReportCard(): Promise<ReportCard> {
  return requestJson(`${API_URL}/classes/student/report-card/`, {
    method: 'GET',
    headers: authHeaders(),
  });
}

export async function getFinishedAnswers(): Promise<FinishedAnswer[]> {
  return requestJson(`${API_URL}/classes/student/exercises/answers/`, {
    method: 'GET',
    headers: authHeaders(),
  });
}

export async function askAssistant(
  sessionId: number,
  exerciseId: number,
  questionId: number,
  message: string
): Promise<AssistantReply> {
  return requestJson(
    `${API_URL}/classes/student/courses/${sessionId}/exercises/${exerciseId}/assistant/`,
    {
      method: 'POST',
      headers: jsonHeaders(),
      body: JSON.stringify({ question_id: questionId, message }),
    }
  );
}

export async function getStudentCalendar(
  from?: string,
  to?: string
): Promise<CalendarEventDto[]> {
  const params = new URLSearchParams();
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  const qs = params.toString();
  return requestJson(`${API_URL}/classes/student/calendar/${qs ? `?${qs}` : ''}`, {
    method: 'GET',
    headers: authHeaders(),
  });
}
