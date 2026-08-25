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
  /** Restart step 3 (wave-2): currently stored source per selected subject,
   * keyed by catalog subject id as a STRING (JSON object keys). Absent key =
   * no source stored yet — read via `resp.selectedSources ?? {}`. */
  selectedSources?: Record<string, string>;
};

/** One selected subject, as it appears on both the advisor `PUT` response and the
 * student's mirror. A catalog fact only — never the engagement it hangs off.
 * `source` is the raw code (`SUBJECT_SOURCE_LABELS` in subject-picker-dialog
 * renders the Persian label); `null` = not chosen yet. */
export type StudentSubjectRow = {
  subjectId: number;
  name: string;
  grade: string | null;
  gradeLabel: string | null;
  isGlobal: boolean;
  source?: string | null;
};

/** `GET /advisory/me/subjects/` — the student's view of what their advisor picked.
 * `active` is false (and `subjects` empty) for every student without an advisor,
 * which is the vast majority; the card renders nothing in that case. */
export type MySubjectsResponse = {
  active: boolean;
  advisorName?: string;
  subjects: StudentSubjectRow[];
};

/** One subject-minute entry of a saved day log. `isSelected: false` marks a
 * subject the advisor later removed from the student's list — its minutes stay
 * in the day (and in the total) so history remains truthful. */
export type StudyLogItem = {
  subjectId: number;
  name: string;
  minutes: number;
  isSelected: boolean;
};

/** The whole-day study log as the server stores it. `mood` is 1..5 or null
 * (not recorded); `totalMinutes` is server-computed over ALL items. */
export type StudyLogDay = {
  date: string;
  mood: number | null;
  note: string;
  /** Restart step 1 (wave-1 unit B): the PDF-derived enrichment. `testPercent`
   * is null when not recorded — distinct from an honest 0. */
  dayGoal: string;
  motivationNote: string;
  testsTaken: number;
  testPercent: number | null;
  items: StudyLogItem[];
  totalMinutes: number;
  updatedAt: string;
};

/** Wire shape shared by GET and PUT of `/advisory/me/study-log/`. `log` is null
 * when nothing was saved for the requested day yet; `minDate`/`maxDate` bound
 * the editable window (null = unbounded on that side). */
export type StudyLogPayload = {
  active: boolean;
  advisorName?: string;
  date: string;
  minDate: string | null;
  maxDate: string | null;
  subjects: StudentSubjectRow[];
  log: StudyLogDay | null;
};

/** PUT body — a WHOLE-day set-replace. Only currently-selected subjects may be
 * sent (server rejects unselected ones); minutes are 0..960 each, duplicates
 * forbidden, day total ≤ 1440, note ≤ 1000 chars, mood int 1..5 or null.
 *
 * The four enrichment keys are the one exception to "absent = cleared": ABSENT
 * leaves the stored value untouched server-side (legacy-payload safety), while
 * PRESENT overwrites wholesale — even with '' / 0 / null. */
export type SaveStudyLogBody = {
  date: string;
  mood?: number | null;
  note?: string;
  dayGoal?: string;
  motivationNote?: string;
  testsTaken?: number;
  testPercent?: number | null;
  items: { subjectId: number; minutes: number }[];
};

/* ── Study feed + study plans (advisor-mvp §14 — variable-horizon redesign) ── */

/** Feed window as the `?days=` query param. `'all'` = since the engagement
 * started; numeric values are clamped server-side to `started_on` (rule C3). */
export type StudyFeedRange = '7' | '14' | '30' | 'all';

/** One subject-minute row of a recorded study day. Restart step 4 adds the
 * plan-slot detail a matching PUBLISHED-plan slot lends the row (`topic`,
 * `unitLabel`, `masteryColor`) plus the «جبران‌نشده» flag; all absent when the
 * item matches no slot or its week has no published plan. A synthetic
 * `uncompensated: true` row with `minutes: 0` is injected for planned-but-
 * unlogged slots so missed commitments surface on their day. */
export type StudyFeedItem = {
  subjectId: number;
  name: string;
  minutes: number;
  topic?: string;
  unitLabel?: string;
  masteryColor?: string | null;
  uncompensated?: boolean;
};

/** One recorded day of the advisor's study feed. Only days with at least one
 * saved log arrive, ascending by `date`; `mood` is 1..5 or null (not recorded). */
export type StudyFeedDay = {
  date: string;
  totalMinutes: number;
  mood: number | null;
  note: string;
  /** Wave-1 unit B: tests taken (> 0 renders the «تست» chip) and exam percent
   * (non-null renders the «درصد» chip). Optional — absent on payloads saved
   * before the enrichment shipped; read via `?? 0` / `?? null`. */
  testsTaken?: number;
  testPercent?: number | null;
  items: StudyFeedItem[];
};

/** Lifecycle of a study plan. Authored as DRAFT, flipped to PUBLISHED on
 * publish; unpublish is the rollback lever back to DRAFT. */
export type StudyPlanStatus = 'DRAFT' | 'PUBLISHED';

/** One planned (subject × day) row of a plan. `date` is the server-derived
 * absolute date (`startDate + dayOffset`) so the client never does calendar math.
 * Restart step 4 adds optional enrichment: `testMinutes` null = no test budget
 * set; `masteryColor` one of RED/YELLOW/GREEN or null. Read via `?? null`. */
export type StudyPlanItemOut = {
  dayOffset: number;
  date: string;
  subjectId: number;
  name: string;
  plannedMinutes: number;
  topic?: string;
  unitLabel?: string;
  testMinutes?: number | null;
  masteryColor?: 'RED' | 'YELLOW' | 'GREEN' | null;
};

/** Shape of one day's note block inside `dayNotes`. */
export type StudyPlanDayNote = Partial<
  Record<'school' | 'exams' | 'konkurClass' | 'preReading', string>
>;

/** Wire shape (`PlanOut`) shared by the feed's embedded plans, `GET …/study-plans`,
 * and the PUT / publish / unpublish responses. */
export type StudyPlanOut = {
  id: number;
  startDate: string;
  endDate: string;
  durationDays: number;
  status: StudyPlanStatus;
  items: StudyPlanItemOut[];
  /** Adherence (step 8): actual ÷ elapsed-planned minutes, rounded int, only
   * for PUBLISHED plans; `null` when no elapsed items exist yet. Absent on
   * older payloads — read via `plan.percent ?? null`. */
  percent?: number | null;
  /** Restart step 4: per-day notes keyed '0'..'6' (strings). Always a dict on
   * the wire; absent on payloads saved before the enrichment shipped. */
  dayNotes?: Record<string, StudyPlanDayNote>;
};

/** `GET /advisory/students/<engagementId>/study-feed/?days=…` — the advisor's
 * read view of one student: recorded days plus the plans intersecting the range.
 * Exactly one AdvisoryAccessLog row is written per successful read (server-side). */
export type StudyFeedResponse = {
  studentName: string;
  range: { from: string; to: string };
  days: StudyFeedDay[];
  plans: StudyPlanOut[];
  /** Step 8: weighted overall adherence across PUBLISHED plans clipped to the
   * selected range (Σactual ÷ Σplanned); `null` when nothing elapsed. */
  adherencePercent?: number | null;
  /** Mean of non-null day moods in range, rounded to 1 decimal; `null` when no
   * mood was recorded at all. */
  moodAverage?: number | null;
};

/** PUT body for `/advisory/students/<engagementId>/study-plan/draft` — a whole
 * draft set-replace (upsert of the single DRAFT slot). `dayOffset` is 0-based
 * and must be `< durationDays`; minutes 1..960; duplicate (day, subject) rows
 * rejected. The UI shows «روز N» where N = dayOffset + 1.
 *
 * Restart step 4: per-row enrichment keys are optional (absent = column
 * default); `dayNotes` is optional at plan level — ABSENT leaves stored notes
 * untouched server-side, PRESENT (even `{}`) replaces them wholesale. */
export type SaveStudyPlanDraftBody = {
  startDate: string;
  durationDays: number;
  items: {
    dayOffset: number;
    subjectId: number;
    plannedMinutes: number;
    topic?: string;
    unitLabel?: string;
    testMinutes?: number | null;
    masteryColor?: 'RED' | 'YELLOW' | 'GREEN' | null;
  }[];
  dayNotes?: Record<string, StudyPlanDayNote>;
};

/** `GET /advisory/me/plans` — the student's PUBLISHED plans only, descending by
 * start date. Quiet like every student-side advisory read: no advisor ⇒ an
 * empty list, never an error. */
export type MyPlansResponse = {
  plans: StudyPlanOut[];
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
    const payload: unknown = await requestJson<unknown>('/advisory/subjects/');
    return Array.isArray(payload) ? (payload as AdvisorySubject[]) : [];
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
   *
   * Restart step 3: `sources` optionally maps subject id → raw source code for
   * ids in THIS request. Keys must be STRINGS (JSON object keys); an absent map
   * leaves every stored source untouched server-side.
   */
  setEngagementSubjects: async (
    engagementId: number,
    subjectIds: number[],
    sources?: Record<string, string>,
  ): Promise<StudentSubjectRow[]> => {
    const body: Record<string, unknown> = { subjectIds };
    if (sources && Object.keys(sources).length > 0) {
      body.sources = sources;
    }
    return requestJson<StudentSubjectRow[]>(
      `/advisory/students/${engagementId}/subjects/`,
      { method: 'PUT', body: JSON.stringify(body) },
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

  /**
   * The student's study log for one day. Omitting `date` means "today".
   * `active: false` (no advisor) arrives as a normal 200 payload, never an
   * error; `409` would only mean the engagement ended between calls and its
   * Persian `detail` surfaces via `requestJson`.
   */
  getMyStudyLog: async (date?: string): Promise<StudyLogPayload> => {
    const query = date ? `?date=${encodeURIComponent(date)}` : '';
    return requestJson<StudyLogPayload>(`/advisory/me/study-log/${query}`);
  },

  /**
   * Save the whole day at once (set-replace, not a patch). The server answers
   * with the same shape as `getMyStudyLog` — callers must re-render from THIS
   * response so server-side normalization (totals, removed subjects) wins over
   * local guesses. Errors are Persian `detail`s via `requestJson`: `409` no
   * active advisor; `400` out-of-window date / unselected subject / day total
   * over 1440 / duplicate subject / per-field over-limit.
   */
  saveMyStudyLog: async (body: SaveStudyLogBody): Promise<StudyLogPayload> => {
    return requestJson<StudyLogPayload>('/advisory/me/study-log/', {
      method: 'PUT',
      body: JSON.stringify(body),
    });
  },

  /**
   * The advisor's read view of one student's study activity for a window.
   * `days='all'` means since the engagement started; numeric windows are
   * clamped server-side to `started_on`. An invalid value answers 400 with
   * «بازه باید یکی از ۷، ۱۴، ۳۰ یا all باشد.»; a foreign/missing engagement
   * answers 404 (never 403) so the pairing's existence never leaks. Each
   * successful read writes exactly one server-side access-log row.
   */
  getStudentStudyFeed: async (
    engagementId: number,
    days: StudyFeedRange,
  ): Promise<StudyFeedResponse> => {
    return requestJson<StudyFeedResponse>(
      `/advisory/students/${engagementId}/study-feed/?days=${encodeURIComponent(days)}`,
    );
  },

  /**
   * Every plan of one student across both statuses, ascending by start date —
   * the advisor's authoring view. Includes the single DRAFT slot when present.
   */
  getStudentPlans: async (engagementId: number): Promise<StudyPlanOut[]> => {
    const payload: unknown = await requestJson<unknown>(
      // Trailing slash MUST match the backend route: without it Django
      // APPEND_SLASH-redirects and fetch downgrades the method to GET (405).
      `/advisory/students/${engagementId}/study-plans/`,
    );
    // The backend answers `{"plans": PlanOut[]}`; a bare array is tolerated so
    // any shape drift degrades to an empty list instead of a runtime crash
    // (`t.find is not a function`) in the planner.
    if (Array.isArray(payload)) return payload as StudyPlanOut[];
    if (
      payload &&
      typeof payload === 'object' &&
      Array.isArray((payload as { plans?: unknown }).plans)
    ) {
      return (payload as { plans: StudyPlanOut[] }).plans;
    }
    return [];
  },

  /**
   * Upsert the single DRAFT slot (whole-body set-replace). Server validation
   * order mirrors save_day: ownership → start ≥ started_on → duration 1..90 →
   * items (offset < duration, active subject, minutes 1..960, no duplicates).
   * Violations answer 400 with their Persian `detail`, surfaced verbatim by
   * `requestJson`. Returns the saved plan as `PlanOut`.
   */
  savePlanDraft: async (
    engagementId: number,
    body: SaveStudyPlanDraftBody,
  ): Promise<StudyPlanOut> => {
    return requestJson<StudyPlanOut>(
      `/advisory/students/${engagementId}/study-plan/draft/`,
      { method: 'PUT', body: JSON.stringify(body) },
    );
  },

  /**
   * Flip the existing draft to PUBLISHED after re-validation. 404 when no
   * draft exists; 400 for an empty plan, an item referencing a since-removed
   * subject, or overlap with another PUBLISHED range (edge-touching allowed).
   */
  publishPlanDraft: async (engagementId: number): Promise<StudyPlanOut> => {
    return requestJson<StudyPlanOut>(
      `/advisory/students/${engagementId}/study-plan/draft/publish/`,
      { method: 'POST' },
    );
  },

  /**
   * Rollback lever: return a PUBLISHED plan to DRAFT so it can be edited and
   * re-published. 404 for a missing/foreign plan id.
   */
  unpublishPlan: async (
    engagementId: number,
    planId: number,
  ): Promise<StudyPlanOut> => {
    return requestJson<StudyPlanOut>(
      `/advisory/students/${engagementId}/study-plan/${planId}/unpublish/`,
      { method: 'POST' },
    );
  },

  /**
   * The student-side mirror: only PUBLISHED plans, descending by start date.
   * Quiet like every student advisory read — no advisor ⇒ `{ plans: [] }`.
   */
  getMyPlans: async (): Promise<MyPlansResponse> => {
    const payload: unknown = await requestJson<unknown>('/advisory/me/plans/');
    if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
      const obj = payload as { plans?: unknown };
      return {
        plans: Array.isArray(obj.plans) ? (obj.plans as StudyPlanOut[]) : [],
      };
    }
    return { plans: [] };
  },
};
