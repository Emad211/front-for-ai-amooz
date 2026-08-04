import {
  ApiRequestError,
  getStoredTokens,
  refreshAccessToken,
} from '@/services/auth-service';

export type ExamPrepSourceAwareBridge = {
  projectId: number;
  sessionId: number;
  documentId: number | null;
  projectStatus: string;
  sessionStatus: string;
};

async function parsePayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function messageFromPayload(payload: unknown): string {
  if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
    const detail = (payload as Record<string, unknown>).detail;
    if (typeof detail === 'string') return detail;
  }
  return 'اطلاعات پردازش آزمون دریافت نشد.';
}

export async function getExamPrepSourceAwareBridge(
  sessionId: number,
  signal?: AbortSignal,
): Promise<ExamPrepSourceAwareBridge | null> {
  let access = getStoredTokens()?.access;
  const request = () => fetch(
    `/api/classes/exam-prep-v4/sessions/${sessionId}/project/`,
    {
      method: 'GET',
      signal,
      credentials: 'include',
      headers: access ? { Authorization: `Bearer ${access}` } : undefined,
    },
  );

  let response = await request();
  if (response.status === 401) {
    access = await refreshAccessToken();
    response = await request();
  }
  if (response.status === 404) return null;

  const payload = await parsePayload(response);
  if (!response.ok) {
    throw new ApiRequestError(
      messageFromPayload(payload),
      response.status,
      payload,
    );
  }
  return payload as ExamPrepSourceAwareBridge;
}
