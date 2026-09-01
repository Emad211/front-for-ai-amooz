/**
 * Parent Service — the API layer for the والد (parent) read-only digest panel.
 *
 * Every parent-panel call goes through here; components never `fetch` directly.
 * Mirrors `advisory-service.ts` (own requestJson, Bearer from the shared
 * localStorage key, one silent refresh retry on 401) and `auth-service.ts`
 * (the two public login POSTs ride the same-origin /api proxy with
 * credentials:include so the HttpOnly refresh cookie stays first-party).
 *
 * The verify call persists tokens + user through auth-service's exported
 * persistTokens/persistUser — the SAME storage keys (`ai_amooz_user`,
 * `userRole`, `ai_amooz_access`) the existing role gates read, so a parent
 * session is indistinguishable from any other role session to the guards.
 */

import {
  persistTokens,
  persistUser,
  refreshAccessToken,
  type AuthMeResponse,
} from '@/services/auth-service';

const RAW_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');

// Accept NEXT_PUBLIC_API_URL with or without the trailing `/api`, same as the
// other services, so a single env value works for all of them.
const API_URL = RAW_API_URL.endsWith('/api') ? RAW_API_URL : `${RAW_API_URL}/api`;

// Same-origin Next.js /api proxy (see next.config.ts) — used only for the two
// public login POSTs, which set the HttpOnly refresh cookie.
const PROXY_API_URL = '/api';

/* ── Wire types (camelCase, exactly per the backend contract) ─────────── */

/** One advisor↔parent link as the parent sees it. `id` keys every later
 * parent route (the digest); `relation` is a code like FATHER/MOTHER/GUARDIAN
 * or an already-Persian label — display mapping is a page concern. */
export type ParentLinkItem = {
  id: number;
  engagementId: number;
  studentName: string;
  advisorName: string;
  relation: string | null;
  status: string;
};

/** One point of the exam-trend mini chart. Both scores are nullable on the
 * wire; the chart draws `scorePercent` only. */
export type ParentExamTrendPoint = {
  date: string;
  scorePercent: number | null;
  tara: number | null;
};

/** `GET /advisory/parent/me/links/<id>/digest/` — the weekly read-only
 * snapshot. Every field is nullable: an absent value renders quiet-neutral
 * (or hides), never a fake 0. */
export type ParentDigest = {
  asOf: string | null;
  weekMinutes: number | null;
  weekPlanMinutes: number | null;
  adherencePercent: number | null;
  testsTaken: number | null;
  examTrend: ParentExamTrendPoint[];
  openMistakesCount: number | null;
  reviewDueCount: number | null;
  activeChallengeTitle: string | null;
  streak: number | null;
};

/** The user object of the verify response (a subset of AuthMeResponse — the
 * parent contract deliberately omits email/avatar and friends). */
export type ParentLoginUser = {
  id: number;
  username: string;
  role: string;
  is_profile_completed: boolean;
  first_name: string | null;
  last_name: string | null;
  phone: string | null;
};

/* ── Defensive normalizers (repo pattern: trust nothing on the wire) ───── */

function nullableString(v: unknown): string | null {
  return typeof v === 'string' && v.trim() ? v : null;
}

function nullableNumber(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === 'object' && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : {};
}

function normalizeLink(raw: unknown): ParentLinkItem | null {
  const obj = asRecord(raw);
  const id = nullableNumber(obj.id);
  if (id === null) return null;
  return {
    id,
    engagementId: nullableNumber(obj.engagementId) ?? id,
    studentName: nullableString(obj.studentName) ?? 'فرزند شما',
    advisorName: nullableString(obj.advisorName) ?? '',
    relation: nullableString(obj.relation),
    status: typeof obj.status === 'string' && obj.status ? obj.status.toUpperCase() : '',
  };
}

function normalizeDigest(raw: unknown): ParentDigest {
  const obj = asRecord(raw);
  const trend: ParentExamTrendPoint[] = [];
  if (Array.isArray(obj.examTrend)) {
    for (const point of obj.examTrend) {
      const p = asRecord(point);
      const date = nullableString(p.date);
      if (date === null) continue;
      trend.push({
        date,
        scorePercent: nullableNumber(p.scorePercent),
        tara: nullableNumber(p.tara),
      });
    }
  }
  return {
    asOf: nullableString(obj.asOf),
    weekMinutes: nullableNumber(obj.weekMinutes),
    weekPlanMinutes: nullableNumber(obj.weekPlanMinutes),
    adherencePercent: nullableNumber(obj.adherencePercent),
    testsTaken: nullableNumber(obj.testsTaken),
    examTrend: trend,
    openMistakesCount: nullableNumber(obj.openMistakesCount),
    reviewDueCount: nullableNumber(obj.reviewDueCount),
    activeChallengeTitle: nullableString(obj.activeChallengeTitle),
    streak: nullableNumber(obj.streak),
  };
}

/* ── requestJson (mirrors advisory-service, plus a public variant) ─────── */

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
    // The contract's errors are Persian `detail`s — surface them verbatim.
    if (typeof obj.detail === 'string' && obj.detail.trim()) return obj.detail;
    if (typeof obj.message === 'string' && obj.message.trim()) return obj.message;
    // DRF serializer errors arrive as {"phone": ["…"]} — surface the first
    // field message instead of collapsing into the generic fallback.
    for (const value of Object.values(obj)) {
      if (typeof value === 'string' && value.trim()) return value;
      if (Array.isArray(value) && typeof value[0] === 'string' && value[0].trim()) {
        return value[0];
      }
    }
  }
  if (typeof payload === 'string' && payload.trim()) return payload;
  return fallback;
}

async function authenticatedRequestJson<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
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

/**
 * Public (session-less) POST through the SAME-ORIGIN /api proxy with
 * credentials:include — mirroring auth-service's baseRequest — so the
 * HttpOnly refresh cookie set by the verify response is first-party.
 */
async function publicPost<T>(path: string, body: Record<string, string>): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${PROXY_API_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error('ارتباط با سرور برقرار نشد.');
  }

  const payload = await parseJson(response);
  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, 'درخواست ناموفق بود.'));
  }
  return payload as T;
}

/* ── API methods ────────────────────────────────────────────────────────── */

/**
 * `POST /advisory/parent/login/request/` — always 202 {"status":"sent"}
 * (no user-enumeration leak). The OTP arrives by SMS («کد ورود والدین: …»).
 */
export async function requestLoginOtp(phone: string): Promise<void> {
  await publicPost<unknown>('/advisory/parent/login/request/', { phone });
}

/**
 * `POST /advisory/parent/login/verify/` — on 200, persists the session with
 * auth-service's own persistTokens/persistUser (same storage keys and
 * `userRole` stamp the role gates read), then returns the logged-in parent.
 * Wrong code → 400 with a Persian `detail`, surfaced verbatim.
 */
export async function verifyLoginOtp(
  phone: string,
  otp: string,
): Promise<ParentLoginUser> {
  const payload = await publicPost<unknown>('/advisory/parent/login/verify/', {
    phone,
    otp,
  });

  const obj = asRecord(payload);
  const access = typeof obj.access === 'string' ? obj.access : '';
  const refresh = typeof obj.refresh === 'string' ? obj.refresh : '';
  const userRaw = asRecord(obj.user);

  if (!access || typeof userRaw.id !== 'number') {
    throw new Error('پاسخ ورود از سرور نامعتبر بود.');
  }

  // Same shape the rest of the app caches: AuthMeResponse minus the fields
  // the parent contract (privacy-first) never sends.
  const user: AuthMeResponse = {
    id: userRaw.id,
    username: typeof userRaw.username === 'string' ? userRaw.username : '',
    first_name: nullableString(userRaw.first_name) ?? '',
    last_name: nullableString(userRaw.last_name) ?? '',
    email: '',
    phone: nullableString(userRaw.phone),
    avatar: null,
    bio: null,
    location: null,
    role:
      typeof userRaw.role === 'string' && userRaw.role ? userRaw.role : 'PARENT',
    is_profile_completed:
      typeof userRaw.is_profile_completed === 'boolean'
        ? userRaw.is_profile_completed
        : true,
  };

  persistTokens({ access, refresh });
  persistUser(user);

  return {
    id: user.id,
    username: user.username,
    role: user.role,
    is_profile_completed: user.is_profile_completed,
    first_name: user.first_name || null,
    last_name: user.last_name || null,
    phone: user.phone ?? null,
  };
}

/** `GET /advisory/parent/me/links/` — the parent's parent↔advisor links. */
export async function getMyLinks(): Promise<ParentLinkItem[]> {
  const payload: unknown = await authenticatedRequestJson<unknown>(
    '/advisory/parent/me/links/',
  );
  const obj = asRecord(payload);
  const links: ParentLinkItem[] = [];
  if (Array.isArray(obj.links)) {
    for (const raw of obj.links) {
      const link = normalizeLink(raw);
      if (link) links.push(link);
    }
  }
  return links;
}

/** `GET /advisory/parent/me/links/<id>/digest/` — the weekly snapshot. */
export async function getDigest(linkId: number): Promise<ParentDigest> {
  const payload: unknown = await authenticatedRequestJson<unknown>(
    `/advisory/parent/me/links/${linkId}/digest/`,
  );
  return normalizeDigest(payload);
}
