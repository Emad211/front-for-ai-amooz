import {
  ApiRequestError,
  getStoredTokens,
  refreshAccessToken,
} from '@/services/auth-service';

const API_ROOT = '/api/classes/exam-prep-v4';

export type ExamPrepV4ReviewQuestion = {
  id: number;
  printedNumber: string | null;
  sectionKey: string | null;
  questionText: string;
  options: Array<{ label: string; text: string }>;
  confidence: number;
  warnings: string[];
};

export type ExamPrepV4ReviewAnswer = {
  id: number;
  printedNumber: string | null;
  sectionKey: string | null;
  correctOption: string | null;
  finalAnswer: string | null;
  solutionText: string | null;
  confidence: number;
  warnings: string[];
};

export type ExamPrepV4TeacherReview = {
  id: number;
  revision: number;
  action: 'match' | 'out_of_scope' | 'ignore';
  questionRecordId: number | null;
  note: string;
  updatedAt: string;
};

export type ExamPrepV4ReviewItem = {
  matchDecisionId: number;
  automaticDecision: string;
  method: string;
  reasonCode: string;
  printedNumber: string | null;
  sectionKey: string | null;
  answer: ExamPrepV4ReviewAnswer;
  review: ExamPrepV4TeacherReview | null;
};

export type ExamPrepV4ReviewQueue = {
  projectId: number;
  projectStatus: string;
  questionSetFingerprint: string;
  answerSetFingerprint: string;
  matchSetFingerprint: string;
  totalCount: number;
  resolvedCount: number;
  remainingCount: number;
  canFinalize: boolean;
  questions: ExamPrepV4ReviewQuestion[];
  items: ExamPrepV4ReviewItem[];
  updatedAt: string;
};

export type ExamPrepV4ReviewDecisionPayload = {
  matchDecisionId: number;
  action: 'match' | 'out_of_scope' | 'ignore';
  questionRecordId?: number | null;
  note?: string;
};

export type ExamPrepV4ReviewDecisionResult = {
  reviewId: number;
  revision: number;
  action: 'match' | 'out_of_scope' | 'ignore';
  questionRecordId: number | null;
  remainingCount: number;
  readyToFinalize: boolean;
  reused: boolean;
};

export type ExamPrepV4ReviewFinalizeResult = {
  projectId: number;
  status: string;
  resolvedCount: number;
  remainingCount: number;
  questionSetFingerprint: string;
  answerSetFingerprint: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

async function parsePayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function safeMessage(payload: unknown, fallback: string): string {
  if (isRecord(payload) && typeof payload.detail === 'string') {
    return payload.detail;
  }
  return fallback;
}

async function authenticatedRequest(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<Response> {
  const headers = new Headers(options.headers);
  const access = getStoredTokens()?.access;
  if (access && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${access}`);
  }
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  let response: Response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      ...options,
      headers,
      credentials: 'include',
    });
  } catch {
    throw new Error('ارتباط با سرور برقرار نشد');
  }
  if (response.status === 401 && retry) {
    const newAccess = await refreshAccessToken();
    headers.set('Authorization', `Bearer ${newAccess}`);
    return authenticatedRequest(path, { ...options, headers }, false);
  }
  return response;
}

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await authenticatedRequest(path, options);
  const payload = await parsePayload(response);
  if (!response.ok) {
    throw new ApiRequestError(
      safeMessage(payload, 'درخواست بازبینی انجام نشد'),
      response.status,
      payload,
    );
  }
  return payload as T;
}

export async function getExamPrepV4ReviewQueue(
  projectId: number,
  signal?: AbortSignal,
): Promise<ExamPrepV4ReviewQueue> {
  return requestJson<ExamPrepV4ReviewQueue>(
    `/projects/${projectId}/review/`,
    { method: 'GET', signal },
  );
}

export async function saveExamPrepV4ReviewDecision(
  projectId: number,
  payload: ExamPrepV4ReviewDecisionPayload,
): Promise<ExamPrepV4ReviewDecisionResult> {
  return requestJson<ExamPrepV4ReviewDecisionResult>(
    `/projects/${projectId}/review/decisions/`,
    { method: 'POST', body: JSON.stringify(payload) },
  );
}

export async function finalizeExamPrepV4Review(
  projectId: number,
  payload: {
    questionSetFingerprint: string;
    answerSetFingerprint: string;
  },
): Promise<ExamPrepV4ReviewFinalizeResult> {
  return requestJson<ExamPrepV4ReviewFinalizeResult>(
    `/projects/${projectId}/review/finalize/`,
    { method: 'POST', body: JSON.stringify(payload) },
  );
}
