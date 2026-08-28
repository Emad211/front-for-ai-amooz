/**
 * Org advisory-panel API module (risman step 3).
 *
 * Separate from `advisory-service.ts` by design (roadmap ق۱۰): each risman
 * step owns its own service module and only reuses the exported `requestJson`
 * helper. Unlike the advisor-facing modules, the manager DOES need an
 * organization id — but only for impersonation (see `impersonation-service.ts`);
 * every panel endpoint here resolves tenancy server-side from the requesting
 * manager's own ACTIVE admin/deputy membership, so the client never sends one.
 */

import { requestJson } from '@/services/advisory-service';

const RAW_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');

// Same normalization `advisory-service.ts` applies: accept the env value with
// or without the trailing `/api`. Without this, the blob download hit
// `:8000/advisory/...` (404) instead of `:8000/api/advisory/...`.
const API_URL = RAW_API_URL.endsWith('/api') ? RAW_API_URL : `${RAW_API_URL}/api`;

/* ── Wire shapes (camelCase mirrors of the backend payloads) ─────────────── */

/** `GET /advisory/org/overview/` — the panel's headline counters. */
export type OrgOverview = {
  activeStudents: number;
  activeAdvisors: number;
  activeEngagements: number;
  weekPlansPublished: number;
  logsToday: number;
  minutesToday: number;
  /** Weighted overall of the current Iranian week; null when nothing planned. */
  avgCommitmentPercent: number | null;
};

/** One student row embedded in its advisor's report row. `engagementId` is
 * the ENGAGEMENT id — the key the reassign endpoint (and nothing else) wants. */
export type OrgAdvisorStudentRow = {
  engagementId: number;
  studentName: string;
  planned: number;
  actual: number;
  coveragePercent: number | null;
  testsTaken: number;
};

/** One advisor row of `GET /advisory/org/advisors/?from=&to=` — sorted by
 * load, then name, server-side. Only advisors holding ≥1 ACTIVE engagement
 * appear (a roster of zero reads as nothing to oversee, not an error). */
export type OrgAdvisorRow = {
  advisorId: number;
  advisorName: string;
  studentCount: number;
  planned: number;
  actual: number;
  coveragePercent: number | null;
  plansPublished: number;
  assessmentsWritten: number;
  analysesCreated: number;
  students: OrgAdvisorStudentRow[];
};

export type OrgAdvisorReport = {
  advisors: OrgAdvisorRow[];
};

/** `POST /advisory/org/engagements/<id>/reassign/` answer. */
export type ReassignResult = {
  engagementId: number;
  advisorId: number;
  advisorName: string;
  studentName: string;
};

/* ── Endpoints ───────────────────────────────────────────────────────────── */

/** Live headline counters of the requesting manager's organization. */
export async function getOrgOverview(): Promise<OrgOverview> {
  return requestJson<OrgOverview>('/advisory/org/overview/');
}

/** Per-advisor aggregates over the inclusive ISO window (max ۹۲ days). */
export async function getOrgAdvisorReport(from: string, to: string): Promise<OrgAdvisorReport> {
  const query = new URLSearchParams({ from, to }).toString();
  return requestJson<OrgAdvisorReport>(`/advisory/org/advisors/?${query}`);
}

/**
 * Move one ACTIVE org engagement to another advisor of the same org.
 * `engagementId` is the ENGAGEMENT id; errors (۴۰۰ business rule, ۴۰۴ stranger)
 * surface their pinned Persian detail via `requestJson`.
 */
export async function reassignEngagement(
  engagementId: number,
  advisorId: number,
): Promise<ReassignResult> {
  return requestJson<ReassignResult>(
    `/advisory/org/engagements/${engagementId}/reassign/`,
    {
      method: 'POST',
      body: JSON.stringify({ advisorId }),
    },
  );
}

/* ── Excel download ──────────────────────────────────────────────────────── */

/**
 * Mirrors `requestJson`'s auth attachment exactly (Bearer access token from
 * local storage): a blob response cannot go through `requestJson`, which
 * parses JSON, so this is the one sanctioned raw-fetch in the feature.
 */
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

async function extractErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const payload: unknown = await response.json();
    if (payload && typeof payload === 'object') {
      const detail = (payload as Record<string, unknown>).detail;
      if (typeof detail === 'string' && detail.trim()) return detail;
    }
  } catch {
    // Non-JSON body — fall through to the generic message.
  }
  return fallback;
}

/**
 * Downloads `report-advisors-<from>_<to>.xlsx` (the §۴.۲ filename rule —
 * also stamped server-side) by fetching the workbook as a blob and handing it
 * to a detached anchor click.
 */
export async function downloadOrgAdvisorReportXlsx(from: string, to: string): Promise<void> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }

  const url = `/advisory/org/advisors/?${new URLSearchParams({ from, to, format: 'xlsx' })}`;

  let response: Response;
  try {
    response = await fetch(`${API_URL}${url}`, {
      headers: { Authorization: `Bearer ${getAccessToken()}` },
    });
  } catch {
    throw new Error('ارتباط با سرور برقرار نشد.');
  }

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, 'دریافت خروجی اکسل ناموفق بود.'));
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = objectUrl;
  anchor.download = `report-advisors-${from}_${to}.xlsx`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}