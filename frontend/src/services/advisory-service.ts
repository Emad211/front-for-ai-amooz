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
  /** `null` for a platform-wide (national) subject. */
  organizationId: number | null;
  organizationName: string | null;
  isGlobal: boolean;
  isActive: boolean;
  /** Grade code, e.g. `'10'`. An identity axis now, not a convenience filter:
   * `null` is a dead/legacy row that derives for nobody (it no longer means
   * "all levels"). */
  grade: string | null;
  gradeLabel: string | null;
  /** Major (رشته) code, e.g. `'math'`. `null` = a *general* subject shared across
   * every major of its grade (دینی/فارسی/…); a set value is major-specific. */
  major: string | null;
  majorLabel: string | null;
};

/** `freelance` = the advisor invited this student directly; `org` = the student
 * arrived through an organization the advisor belongs to. */
export type EngagementMode = 'freelance' | 'org';

/** Lifecycle status as it appears on the wire. Only ACTIVE ever reaches the
 * student roster; PENDING only reaches the outbox and the student's banner. */
export type EngagementStatus = 'PENDING' | 'ACTIVE' | 'REJECTED' | 'ENDED';

/** An accepted student, as their advisor sees them. `id` is the ENGAGEMENT id,
 * never the student's user id — every later advisory route is keyed by it. */
export type AdvisorStudent = {
  id: number;
  studentName: string;
  phoneMasked: string;
  mode: EngagementMode;
  organizationName: string | null;
  /** ISO date (`YYYY-MM-DD`) the collaboration began, or `null` if not started. */
  startedOn: string | null;
  status: EngagementStatus;
};

/** The advisor's outbox: an invite with the invitee deliberately stripped out —
 * only the masked number the advisor themselves typed. No name, no id. */
export type AdvisorPendingInvite = {
  id: number;
  phoneMasked: string;
  invitedAt: string;
  expiresAt: string | null;
  isExpired: boolean;
};

/** `GET /advisory/students/` — roster and outbox arrive together. */
export type AdvisorStudentsResponse = {
  students: AdvisorStudent[];
  pendingInvites: AdvisorPendingInvite[];
};

/** A pending invite as the STUDENT sees it — the accept-banner payload. */
export type StudentInvite = {
  id: number;
  advisorName: string;
  invitedPhoneMasked: string;
  mode: EngagementMode;
  organizationName: string | null;
  invitedAt: string;
  expiresAt: string | null;
};

/** The student's current advisor, if they have one. */
export type StudentEngagement = {
  id: number;
  advisorName: string;
  mode: EngagementMode;
  organizationName: string | null;
  startedOn: string | null;
  status: EngagementStatus;
};

/** `GET /advisory/me/engagement/` — drives both the dashboard section and the
 * accept banner from one call. */
export type StudentEngagementResponse = {
  active: StudentEngagement | null;
  invites: StudentInvite[];
};

/** `GET /advisory/students/<engagementId>/subjects/` — what the picker opens with.
 * `subjects` is the student's **server-derived curriculum** (the candidates the
 * advisor may focus), computed from the student's own `(grade, major)`; the axes are
 * echoed back only for the header and gate nothing on the client. `studentGrade`
 * being `null` means the student has not set a grade, so nothing was derived. */
export type EngagementSubjectsResponse = {
  studentGrade: string | null;
  studentGradeLabel: string | null;
  studentMajor: string | null;
  studentMajorLabel: string | null;
  subjects: AdvisorySubject[];
  selectedSubjectIds: number[];
};

/** One selected subject, as it appears on both the advisor `PUT` response and the
 * student's mirror. A catalog fact only — never the engagement it hangs off. */
export type StudentSubjectRow = {
  subjectId: number;
  name: string;
  grade: string | null;
  gradeLabel: string | null;
  isGlobal: boolean;
};

/** `GET /advisory/me/subjects/` — the student's view of what their advisor picked.
 * `active` is false (and `subjects` empty) for every student without an advisor,
 * which is the vast majority; the card renders nothing in that case. */
export type MySubjectsResponse = {
  active: boolean;
  advisorName?: string;
  subjects: StudentSubjectRow[];
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
    // DRF serializer errors arrive as {"phone": ["…"]}. The invite endpoint's
    // 400 (mal-shaped number) uses exactly this shape, so surface the first
    // field message rather than collapsing every validation error into the
    // generic fallback — an advisor who typed «۰۹۱۲» must be told that.
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

  /**
   * The advisor's roster (accepted students) and outbox (unanswered invites),
   * in one call — they are one screen, and splitting them buys only a second
   * loading state. Neither list is paginated; both are bounded server-side.
   */
  getStudents: async (): Promise<AdvisorStudentsResponse> => {
    return requestJson<AdvisorStudentsResponse>('/advisory/students/');
  },

  /**
   * Invite a student by phone. The backend answers `202 {"status":"sent"}` for
   * every well-formed number regardless of whether it belongs to anyone — that
   * uniformity is a security property (B2), so the UI must treat success as
   * "the invite was queued", never "a student was found". A `400` means the
   * number itself is mal-shaped; `429`/`503` are quota/breaker limits, whose
   * Persian `detail` is surfaced verbatim by `requestJson`.
   */
  createInvite: async (phone: string): Promise<{ status: string }> => {
    return requestJson<{ status: string }>('/advisory/invites/', {
      method: 'POST',
      body: JSON.stringify({ phone }),
    });
  },

  /**
   * "Do I have an advisor, and are there invites waiting?" — the student-side
   * read. `active` and `invites` are both empty for the vast majority of
   * students; the existence of an active engagement is what gates the advisory
   * UI, since the repo has no separate feature flag.
   */
  getMyEngagement: async (): Promise<StudentEngagementResponse> => {
    return requestJson<StudentEngagementResponse>('/advisory/me/engagement/');
  },

  /**
   * Accept an invite — grants the advisor read access from **today** on. `404`
   * for an invite that is missing/expired/addressed to a different number,
   * `409` if the student already has an active advisor or already accepted.
   */
  acceptInvite: async (inviteId: number): Promise<StudentEngagement> => {
    return requestJson<StudentEngagement>(
      `/advisory/me/invites/${inviteId}/accept/`,
      { method: 'POST' },
    );
  },

  /**
   * Decline an invite. Terminal: the same advisor cannot re-invite for 30 days.
   */
  rejectInvite: async (inviteId: number): Promise<{ status: string }> => {
    return requestJson<{ status: string }>(
      `/advisory/me/invites/${inviteId}/reject/`,
      { method: 'POST' },
    );
  },

  /**
   * Open the picker for one student: returns their server-derived curriculum
   * (`subjects`, the candidates the advisor may focus), the currently selected
   * subset, and the student's axes for the header. `engagementId` is the
   * ENGAGEMENT id (`AdvisorStudent.id`), never a user id. `404` for an engagement
   * that is missing or belongs to another advisor — the caller shows a "not found",
   * never a "forbidden", so the existence of the pairing never leaks.
   */
  getEngagementSubjects: async (
    engagementId: number,
  ): Promise<EngagementSubjectsResponse> => {
    return requestJson<EngagementSubjectsResponse>(
      `/advisory/students/${engagementId}/subjects/`,
    );
  },

  /**
   * Replace a student's subject set wholesale (not append): whatever is omitted is
   * deactivated server-side, an empty array clears the selection. Returns the new
   * active set. `409` if the engagement is not ACTIVE, `400` for a subject the
   * advisor may not assign — both surface their Persian `detail` via `requestJson`.
   */
  setEngagementSubjects: async (
    engagementId: number,
    subjectIds: number[],
  ): Promise<StudentSubjectRow[]> => {
    return requestJson<StudentSubjectRow[]>(
      `/advisory/students/${engagementId}/subjects/`,
      { method: 'PUT', body: JSON.stringify({ subjectIds }) },
    );
  },

  /**
   * The student-side mirror: "what did my advisor pick for me?" Quiet like
   * `getMyEngagement` — a student with no active advisor gets
   * `{ active: false, subjects: [] }`, never an error, so the card can render
   * nothing without special-casing a failure.
   */
  getMySubjects: async (): Promise<MySubjectsResponse> => {
    return requestJson<MySubjectsResponse>('/advisory/me/subjects/');
  },
};
