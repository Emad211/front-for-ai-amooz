import {
  ApiRequestError,
  getStoredTokens,
  refreshAccessToken,
} from '@/services/auth-service';

const API_ROOT = '/api/classes/exam-prep-v4';

export type ExamPrepV4ProjectionResult = {
  projectId: number;
  sessionId: number;
  projectionId: number;
  projectionFingerprint: string;
  questionCount: number;
  status: 'ready' | 'published' | 'superseded' | 'failed';
  published: boolean;
  reused: boolean;
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

async function requestJson<T>(path: string): Promise<T> {
  const headers = new Headers({ 'Content-Type': 'application/json' });
  const access = getStoredTokens()?.access;
  if (access) headers.set('Authorization', `Bearer ${access}`);

  let response: Response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      method: 'POST',
      body: JSON.stringify({}),
      headers,
      credentials: 'include',
    });
  } catch {
    throw new Error('ارتباط با سرور برقرار نشد');
  }

  if (response.status === 401) {
    const newAccess = await refreshAccessToken();
    headers.set('Authorization', `Bearer ${newAccess}`);
    response = await fetch(`${API_ROOT}${path}`, {
      method: 'POST',
      body: JSON.stringify({}),
      headers,
      credentials: 'include',
    });
  }

  const payload = await parsePayload(response);
  if (!response.ok) {
    const detail = isRecord(payload) && typeof payload.detail === 'string'
      ? payload.detail
      : 'عملیات projection انجام نشد';
    throw new ApiRequestError(detail, response.status, payload);
  }
  return payload as T;
}

export async function buildExamPrepV4Projection(
  projectId: number,
): Promise<ExamPrepV4ProjectionResult> {
  return requestJson<ExamPrepV4ProjectionResult>(
    `/projects/${projectId}/projection/`,
  );
}

export async function publishExamPrepV4Project(
  projectId: number,
): Promise<ExamPrepV4ProjectionResult> {
  return requestJson<ExamPrepV4ProjectionResult>(
    `/projects/${projectId}/publish/`,
  );
}
