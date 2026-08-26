/**
 * Advisory reports API module (risman step 2).
 *
 * Separate from `advisory-service.ts` by design (roadmap ق۱۰): each risman
 * step owns its own service module and only reuses the exported `requestJson`
 * helper, so parallel agents never touch the shared file. Every call is keyed
 * by ENGAGEMENT id — the same tenancy key every advisory route uses.
 */

import { requestJson } from '@/services/advisory-service';

const RAW_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');

/* ── Wire shapes (camelCase mirrors of the backend payloads) ─────────────── */

/** One day row of the planner report. Dates are ISO `YYYY-MM-DD`. */
export type PlannerReportDay = {
  date: string;
  planned: number;
  actual: number;
};

/** One subject row of the planner report. `coveragePercent` is quiet-null
 * when nothing was planned («ثبت نشده», never a fake 0%). */
export type PlannerReportSubject = {
  subjectId: number;
  name: string;
  planned: number;
  actual: number;
  coveragePercent: number | null;
};

export type PlannerReportTotals = {
  planned: number;
  actual: number;
  coveragePercent: number | null;
};

/** `GET /advisory/students/<id>/reports/planner/?from=&to=` */
export type PlannerReport = {
  days: PlannerReportDay[];
  subjects: PlannerReportSubject[];
  totals: PlannerReportTotals;
};

export type StudentStudyPoint = { date: string; minutes: number };
export type StudentTestPoint = { date: string; testsTaken: number };

export type SubjectShareItem = {
  subjectId: number;
  name: string;
  minutes: number;
  sharePercent: number | null;
};

/** Same shape the exam-scores card already renders (shared serializer). */
export type ReportExamScoreItem = {
  id: number;
  title: string;
  subjectId: number | null;
  subjectName: string | null;
  examKind: string;
  examDate: string;
  scorePercent: number;
  tara: number | null;
  advisorRating: string | null;
  advisorNote: string;
};

/** `GET /advisory/students/<id>/reports/student/?from=&to=` */
export type StudentReport = {
  studySeries: StudentStudyPoint[];
  testSeries: StudentTestPoint[];
  subjectShare: SubjectShareItem[];
  examScores: ReportExamScoreItem[];
};

/* ── Endpoints ───────────────────────────────────────────────────────────── */

function reportsUrl(path: string, params: Record<string, string>): string {
  return `${path}?${new URLSearchParams(params).toString()}`;
}

/** The planner report (planned-vs-actual) over an inclusive ISO range. */
export async function getPlannerReport(
  engagementId: number,
  from: string,
  to: string,
): Promise<PlannerReport> {
  return requestJson<PlannerReport>(
    reportsUrl(`/advisory/students/${engagementId}/reports/planner/`, { from, to }),
  );
}

/** The student report (study/test series, subject share, exam scores). */
export async function getStudentReport(
  engagementId: number,
  from: string,
  to: string,
): Promise<StudentReport> {
  return requestJson<StudentReport>(
    reportsUrl(`/advisory/students/${engagementId}/reports/student/`, { from, to }),
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
 * Downloads `report-planner-<from>_<to>.xlsx` (the §۴.۲ filename rule) by
 * fetching the workbook as a blob and handing it to a detached anchor click.
 */
export async function downloadPlannerReportXlsx(
  engagementId: number,
  from: string,
  to: string,
): Promise<void> {
  if (!RAW_API_URL) {
    throw new Error('NEXT_PUBLIC_API_URL تنظیم نشده است.');
  }

  const url = reportsUrl(`${RAW_API_URL}/advisory/students/${engagementId}/reports/planner/`, {
    from,
    to,
    format: 'xlsx',
  });

  let response: Response;
  try {
    response = await fetch(url, {
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
  anchor.download = `report-planner-${from}_${to}.xlsx`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}
