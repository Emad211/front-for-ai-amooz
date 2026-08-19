/**
 * Advisory Service — the API layer for the مشاور (advisor) panel.
 *
 * Every advisor-panel call goes through here; components never `fetch` directly.
 * Kept separate from `organization-service` on purpose: an advisor's tenancy is
 * resolved server-side from their org membership, so the client never sends an
 * organization id and must never learn to.
 */

const RAW_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');

// Accept NEXT_PUBLIC_API_URL with or without the trailing `/api`, same as the
// other services, so a single env value works for all of them.
const API_URL = RAW_API_URL.endsWith('/api') ? RAW_API_URL : `${RAW_API_URL}/api`;

import { refreshAccessToken } from '@/services/auth-service';

/** A row of the subject catalog as the advisor picker sees it. */
export type AdvisorySubject = {
  id: number;
  name: string;
  /** `null` for a platform-wide subject. */
  organizationId: number | null;
  organizationName: string | null;
  isGlobal: boolean;
  isActive: boolean;
};

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

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (payload && typeof payload === 'object') {
    const obj = payload as Record<string, unknown>;
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
  headers.set('Authorization', `Bearer ${getAccessToken()}`);
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json');
  }

  const url = `${API_URL}${path}`;
  const doFetch = async (reqHeaders: Headers) => {
    try {
      return await fetch(url, { ...options, headers: reqHeaders });
    } catch {
      throw new Error('ارتباط با سرور برقرار نشد.');
    }
  };

  let response = await doFetch(headers);
  let payload = await parseJson(response);

  // A short access token expiring mid-session must not read as a permission
  // error: retry once with a fresh one before surfacing anything to the user.
  if (response.status === 401) {
    try {
      const newAccess = await refreshAccessToken();
      headers.set('Authorization', `Bearer ${newAccess}`);
      response = await doFetch(headers);
      payload = await parseJson(response);
    } catch {
      // refreshAccessToken() already clears storage and redirects to /login.
    }
  }

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, 'درخواست ناموفق بود.'));
  }
  return payload as T;
}

export const AdvisoryService = {
  /**
   * Subjects this advisor may assign: the platform-wide catalog plus the
   * private catalog of every organization they actively advise for. The
   * endpoint is unpaginated by design — it feeds a picker, and a silently
   * truncated picker is a bug.
   */
  getSubjects: async (): Promise<AdvisorySubject[]> => {
    return requestJson<AdvisorySubject[]>('/advisory/subjects/');
  },
};
