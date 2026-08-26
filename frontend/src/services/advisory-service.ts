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

/* ── Advisor home cockpit (`GET /advisory/overview/`) ─────────────────── */

/** Headline counters for the advisor dashboard. `averageAdherence7d` is the
 * mean of per-student 7-day adherence (rounded int) or `null` when no student
 * has any recorded plan activity — quiet-null, never a fake 0%. */
export type AdvisorOverviewMetrics = {
  activeStudents: number;
  pendingInvites: number;
  averageAdherence7d: number | null;
};

/** One enrichment row of the overview, keyed by ENGAGEMENT id — join it to
 * `AdvisorStudent.id` on the client. Every field is nullable: a student with
 * no published plan this week simply has `adherence7d: null`. */
export type AdvisorOverviewStudentRow = {
  engagementId: number;
  adherence7d: number | null;
  /** ISO date (`YYYY-MM-DD`) of the student's most recent study log. */
  lastLogDate: string | null;
  /** Title of one currently-ACTIVE challenge, or `null`. */
  activeChallengeTitle: string | null;
};

/** `GET /advisory/overview/` — metrics plus per-student enrichment rows. */
export type AdvisorOverviewResponse = {
  metrics: AdvisorOverviewMetrics;
  students: AdvisorOverviewStudentRow[];
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

/* ── Restart wave 3: intake (step 2), weekly assessments (step 7), call logs (step 10) ── */

/** One class row of the intake form. `weekday` is 0=شنبه..6=جمعه; `startTime`/
 * `endTime` are `HH:MM` strings or null when unset. */
export type IntakeClass = {
  name: string;
  teacher: string;
  weekday: number;
  startTime: string | null;
  endTime: string | null;
  order: number;
};

/** Restart step 2 — the whole «شناخت» profile. Every PUT is a WHOLE set-replace:
 * whatever the payload omits is cleared server-side, classes included. */
export type IntakePayload = {
  school: string;
  city: string;
  /** Decimal 0..20 or null when not recorded — null is distinct from 0. */
  lastGpa: number | null;
  targetMajor: string;
  targetUniversity: string;
  mockExamInstitute: string;
  /** Minutes 0..1440 or null when not recorded. */
  freeDayMinutes: number | null;
  classes: IntakeClass[];
};

/** `GET|PUT /advisory/me/intake/` — the student-side mirror. `active:false`
 * (no advisor) arrives as a normal 200 with `intake:null`; PUT without an
 * active advisor answers 409 «ابتدا مشاور خود را تأیید کنید.» */
export type MyIntakeResponse = {
  active: boolean;
  intake: IntakePayload | null;
};

/** One of the 15 weekly-assessment criteria, serialized from the backend's
 * canonical list — the client NEVER hardcodes labels, it renders from this. */
export type WeeklyAssessmentCriterion = {
  code: string;
  label: string;
};

/** One saved week of the advisor's weekly assessment. `scores` maps criterion
 * code → int 1..5; `average` is the server-computed mean (or null). */
export type WeeklyAssessmentItem = {
  weekStart: string;
  scores: Record<string, number>;
  advisorSummary: string;
  average: number | null;
};

/** `GET /advisory/students/<engagementId>/weekly-assessments/` — criteria meta
 * plus saved weeks, descending by `weekStart`. */
export type WeeklyAssessmentsResponse = {
  criteria: WeeklyAssessmentCriterion[];
  assessments: WeeklyAssessmentItem[];
};

/** PUT body for one week's upsert (unique per engagement+weekStart). The
 * backend requires ALL criteria scored 1..5 — an incomplete map answers 400
 * naming the missing criterion. */
export type SaveWeeklyAssessmentBody = {
  scores: Record<string, number>;
  advisorSummary: string;
};

/** One row of the weekly call-log plan. `callDate` is ISO or null when the
 * call has not been dated yet. */
export type CallLogItem = {
  weekStart: string;
  done: boolean;
  callDate: string | null;
  topic: string;
  note: string;
};

/** `GET /advisory/students/<engagementId>/call-logs/` — the four most recent
 * weeks, absent ones filled virtually with `done:false`. */
export type CallLogsResponse = {
  weeks: CallLogItem[];
};

/** PUT body for one call-log row upsert. Keys ride along explicitly every time
 * (repo-wide set-replace posture): a cleared field is sent as ''/null, not
 * omitted, so "absent = keep stored" ambiguity never arises. */
export type SaveCallLogBody = {
  done: boolean;
  callDate?: string | null;
  topic?: string;
  note?: string;
};

/* ── Restart wave 4: exam scores (step 5) + exam analyses (step 6) ── */

/** Kind of an exam score row, as stored on the wire. */
export type ExamScoreKind =
  | 'SCHOOL'
  | 'PERSONAL'
  | 'CLASS_C'
  | 'ONLINE'
  | 'NATIONAL'
  | 'ADVISOR';

/** The advisor's qualitative verdict on one exam. */
export type ExamScoreRating = 'EXCELLENT' | 'GOOD' | 'FAIR' | 'WEAK';

/** Grade band of an exam-analysis report card. */
export type ExamGradeBand = 'G10' | 'G11' | 'G12S1' | 'G12S2';

/** One saved exam score (restart step 5). `examDate` is ISO `YYYY-MM-DD`
 * (Jalali display is a client concern — never send Jalali strings);
 * `scorePercent` is 0..100; `tara` (تراز) and the rating are optional. */
export type ExamScore = {
  id: number;
  title: string;
  /** Optional link into the subject catalog; not wired in the v1 UI. */
  subjectId: number | null;
  subjectName: string | null;
  examKind: ExamScoreKind;
  examDate: string;
  scorePercent: number;
  tara: number | null;
  advisorRating: ExamScoreRating | null;
  advisorNote: string;
};

/** POST body for a new exam score. */
export type CreateExamScoreBody = {
  title: string;
  examKind: ExamScoreKind;
  examDate: string;
  scorePercent: number;
  tara?: number | null;
  advisorRating?: ExamScoreRating | null;
  advisorNote?: string;
  subjectId?: number | null;
};

/** PATCH body for one score — the UI sends ONLY the keys that changed. */
export type UpdateExamScoreBody = Partial<CreateExamScoreBody>;

/** One subject row of an exam analysis. All counts are ≥ 0 integers;
 * `subjectName` is free text (every institute names subjects its own way). */
export type ExamAnalysisRow = {
  subjectName: string;
  wrongCount: number;
  skippedCount: number;
  doubtfulTotal: number;
  doubtfulWrong: number;
  doubtfulSkipped: number;
  doubtfulCorrect: number;
  causeNote: string;
};

/** One per-question note of an exam analysis; question numbers are unique
 * per analysis (server UniqueConstraint) and bounded 1..300. */
export type ExamAnalysisNote = {
  questionNumber: number;
  subjectName: string;
  note: string;
};

/** One saved exam analysis / report card (restart step 6). Every metric is
 * optional on the wire; `rows`/`notes` always arrive as arrays. */
export type ExamAnalysis = {
  id: number;
  examNumber: number | null;
  examDate: string | null;
  gradeBand: ExamGradeBand | null;
  totalTara: number | null;
  nationalRank: number | null;
  regionRank: number | null;
  cityRank: number | null;
  highestPercent: number | null;
  lowestPercent: number | null;
  taraDelta: number | null;
  advisorReport: string;
  rows: ExamAnalysisRow[];
  notes: ExamAnalysisNote[];
};

/** POST body for a new analysis, and the WHOLE body of every PUT — PUT is a
 * set-replace: rows and notes ride along in full, whatever is omitted is
 * deleted server-side. */
export type ExamAnalysisWriteBody = {
  examNumber?: number | null;
  examDate?: string | null;
  gradeBand?: ExamGradeBand | null;
  totalTara?: number | null;
  nationalRank?: number | null;
  regionRank?: number | null;
  cityRank?: number | null;
  highestPercent?: number | null;
  lowestPercent?: number | null;
  taraDelta?: number | null;
  advisorReport?: string;
  rows: ExamAnalysisRow[];
  notes: ExamAnalysisNote[];
};

/** `GET /advisory/me/exam-scores/` — the student mirror. Quiet: no active
 * advisor ⇒ `{ active: false, scores: [] }`, never an error. */
export type MyExamScoresResponse = {
  active: boolean;
  scores: ExamScore[];
};

/** `GET /advisory/me/exam-analyses/` — the student mirror, same quiet rule. */
export type MyExamAnalysesResponse = {
  active: boolean;
  analyses: ExamAnalysis[];
};

/* ── Restart wave 5: monthly outlook (step 8) + 7-day challenges (step 9) ── */

/** Who executes a monthly strategy slot. */
export type MonthlyOutlookExecutor = 'ADVISOR' | 'STUDENT';

/** One dated row of the monthly calendar («مناسبت / تقویم تحصیلی / کارها»). */
export type MonthlyOutlookEntry = {
  /** ISO `YYYY-MM-DD` Gregorian. May legally fall outside the month — the
   * server does not clamp it (borderline academic-calendar days are allowed). */
  date: string;
  event: string;
  academicNote: string;
  tasks: string;
};

/** One numbered strategy slot of the month; the UI renders positions 1..4. */
export type MonthlyStrategy = {
  position: number;
  title: string;
  executor: MonthlyOutlookExecutor;
  body: string;
};

/** Whole monthly-outlook payload — the GET answer AND the WHOLE PUT body
 * alike. `monthStart` is the GREGORIAN first day of the chosen Jalali month
 * (the client converts via date-fns-jalali; a Jalali string never crosses the
 * wire). Every PUT is a set-replace: omitted entries/strategies are deleted. */
export type MonthlyOutlook = {
  monthStart: string;
  entries: MonthlyOutlookEntry[];
  strategies: MonthlyStrategy[];
};

/** `GET /advisory/me/monthly-outlooks/<monthStart>/` — quiet student mirror. */
export type MyMonthlyOutlookResponse = {
  active: boolean;
  outlook: MonthlyOutlook | null;
};

/** Lifecycle of a 7-day challenge. ACTIVE→DONE/CANCELLED is one-way; flipping
 * a terminal status back answers 409 with its Persian detail. */
export type ChallengeStatus = 'ACTIVE' | 'DONE' | 'CANCELLED';

/** One day of a challenge. `dayNumber` is 1..7; the absolute date is derived
 * client-side as `startDate + dayNumber - 1` and never sent on the wire. */
export type ChallengeDay = {
  dayNumber: number;
  goal: string;
  summary: string;
};

/** One saved challenge (restart step 9). `endDate` is ALWAYS server-derived
 * (`startDate + 6`) — the client never sends it, on create or anywhere else. */
export type Challenge = {
  id: number;
  title: string;
  goalText: string;
  dailyRoutine: string;
  executionNote: string;
  observer: string;
  problemTarget: string;
  startDate: string;
  endDate: string;
  status: ChallengeStatus;
  days: ChallengeDay[];
};

/** POST body for a new challenge. `endDate` deliberately absent — deriving it
 * is the server's job. A fourth concurrently-ACTIVE challenge answers 400
 * «حداکثر ۳ چالش فعال…» whose Persian detail surfaces verbatim. */
export type CreateChallengeBody = {
  title: string;
  goalText?: string;
  dailyRoutine?: string;
  executionNote?: string;
  observer?: string;
  problemTarget?: string;
  startDate: string;
};

/** PATCH body for one challenge — metadata keys and/or `status`; every key
 * absent from the patch stays exactly as stored server-side. */
export type UpdateChallengeBody = Partial<CreateChallengeBody> & {
  status?: ChallengeStatus;
};

/** Advisor PUT body for `…/days/` — a WHOLE set-replace of the 7 days. */
export type SaveChallengeDaysBody = ChallengeDay[];

/** Student PUT body for `me/challenges/<id>/days/`. Same shape as the advisor's,
 * but the server accepts ONLY goal/summary — any other field ⇒ 400
 * «فقط هدف و خلاصهٔ روز را می‌توانید ثبت کنید.» */
export type StudentChallengeDayBody = {
  dayNumber: number;
  goal: string;
  summary: string;
};

/** `GET /advisory/me/challenges/` — quiet student mirror. */
export type MyChallengesResponse = {
  active: boolean;
  challenges: Challenge[];
};

/** Coerce an unknown wire payload into a safe `IntakePayload` (the t.find
 * regression lesson: never trust list/object shapes). */
function normalizeIntakePayload(payload: unknown): IntakePayload {
  const obj =
    payload && typeof payload === 'object'
      ? (payload as Record<string, unknown>)
      : {};
  const rawClasses = Array.isArray(obj.classes) ? obj.classes : [];
  const classes: IntakeClass[] = [];
  for (const raw of rawClasses) {
    if (!raw || typeof raw !== 'object') continue;
    const c = raw as Record<string, unknown>;
    classes.push({
      name: typeof c.name === 'string' ? c.name : '',
      teacher: typeof c.teacher === 'string' ? c.teacher : '',
      weekday: typeof c.weekday === 'number' ? c.weekday : 0,
      startTime: typeof c.startTime === 'string' && c.startTime ? c.startTime : null,
      endTime: typeof c.endTime === 'string' && c.endTime ? c.endTime : null,
      order: typeof c.order === 'number' ? c.order : 0,
    });
  }
  return {
    school: typeof obj.school === 'string' ? obj.school : '',
    city: typeof obj.city === 'string' ? obj.city : '',
    lastGpa: typeof obj.lastGpa === 'number' ? obj.lastGpa : null,
    targetMajor: typeof obj.targetMajor === 'string' ? obj.targetMajor : '',
    targetUniversity:
      typeof obj.targetUniversity === 'string' ? obj.targetUniversity : '',
    mockExamInstitute:
      typeof obj.mockExamInstitute === 'string' ? obj.mockExamInstitute : '',
    freeDayMinutes:
      typeof obj.freeDayMinutes === 'number' ? obj.freeDayMinutes : null,
    classes,
  };
}

function normalizeMyIntake(payload: unknown): MyIntakeResponse {
  const obj =
    payload && typeof payload === 'object'
      ? (payload as Record<string, unknown>)
      : {};
  return {
    active: obj.active === true,
    intake: obj.intake == null ? null : normalizeIntakePayload(obj.intake),
  };
}

function normalizeWeeklyAssessmentItem(
  payload: unknown,
): WeeklyAssessmentItem | null {
  if (!payload || typeof payload !== 'object') return null;
  const obj = payload as Record<string, unknown>;
  const scores: Record<string, number> = {};
  if (obj.scores && typeof obj.scores === 'object') {
    for (const [code, value] of Object.entries(
      obj.scores as Record<string, unknown>,
    )) {
      if (typeof value === 'number') scores[code] = value;
    }
  }
  return {
    weekStart: typeof obj.weekStart === 'string' ? obj.weekStart : '',
    scores,
    advisorSummary: typeof obj.advisorSummary === 'string' ? obj.advisorSummary : '',
    average: typeof obj.average === 'number' ? obj.average : null,
  };
}

function normalizeWeeklyAssessments(payload: unknown): WeeklyAssessmentsResponse {
  const obj =
    payload && typeof payload === 'object'
      ? (payload as Record<string, unknown>)
      : {};
  const criteria: WeeklyAssessmentCriterion[] = [];
  if (Array.isArray(obj.criteria)) {
    for (const raw of obj.criteria) {
      if (!raw || typeof raw !== 'object') continue;
      const c = raw as Record<string, unknown>;
      if (typeof c.code === 'string' && typeof c.label === 'string') {
        criteria.push({ code: c.code, label: c.label });
      }
    }
  }
  const assessments: WeeklyAssessmentItem[] = [];
  if (Array.isArray(obj.assessments)) {
    for (const raw of obj.assessments) {
      const item = normalizeWeeklyAssessmentItem(raw);
      if (item) assessments.push(item);
    }
  }
  return { criteria, assessments };
}

function normalizeCallLogItem(payload: unknown): CallLogItem | null {
  if (!payload || typeof payload !== 'object') return null;
  const obj = payload as Record<string, unknown>;
  return {
    weekStart: typeof obj.weekStart === 'string' ? obj.weekStart : '',
    done: obj.done === true,
    callDate: typeof obj.callDate === 'string' && obj.callDate ? obj.callDate : null,
    topic: typeof obj.topic === 'string' ? obj.topic : '',
    note: typeof obj.note === 'string' ? obj.note : '',
  };
}

/* ── Restart wave 4 normalizers ──────────────────────────────────────── */

const EXAM_SCORE_KINDS: readonly ExamScoreKind[] = [
  'SCHOOL',
  'PERSONAL',
  'CLASS_C',
  'ONLINE',
  'NATIONAL',
  'ADVISOR',
];

const EXAM_SCORE_RATINGS: readonly ExamScoreRating[] = [
  'EXCELLENT',
  'GOOD',
  'FAIR',
  'WEAK',
];

const EXAM_GRADE_BANDS: readonly ExamGradeBand[] = [
  'G10',
  'G11',
  'G12S1',
  'G12S2',
];

function nullableNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function nullableString(value: unknown): string | null {
  return typeof value === 'string' && value ? value : null;
}

function coerceEnum<T extends string>(
  value: unknown,
  allowed: readonly T[],
  fallback: T,
): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

function nullableEnum<T extends string>(
  value: unknown,
  allowed: readonly T[],
): T | null {
  return allowed.includes(value as T) ? (value as T) : null;
}

function normalizeExamScore(payload: unknown): ExamScore | null {
  if (!payload || typeof payload !== 'object') return null;
  const obj = payload as Record<string, unknown>;
  const id = nullableNumber(obj.id);
  if (id === null) return null;
  return {
    id,
    title: typeof obj.title === 'string' ? obj.title : '',
    subjectId: nullableNumber(obj.subjectId),
    subjectName: nullableString(obj.subjectName),
    examKind: coerceEnum(obj.examKind, EXAM_SCORE_KINDS, 'SCHOOL'),
    examDate: typeof obj.examDate === 'string' ? obj.examDate : '',
    scorePercent: nullableNumber(obj.scorePercent) ?? 0,
    tara: nullableNumber(obj.tara),
    advisorRating: nullableEnum(obj.advisorRating, EXAM_SCORE_RATINGS),
    advisorNote: typeof obj.advisorNote === 'string' ? obj.advisorNote : '',
  };
}

function normalizeExamScoreList(payload: unknown): ExamScore[] {
  if (!Array.isArray(payload)) return [];
  const list: ExamScore[] = [];
  for (const raw of payload) {
    const item = normalizeExamScore(raw);
    if (item) list.push(item);
  }
  return list;
}

function normalizeExamAnalysis(payload: unknown): ExamAnalysis | null {
  if (!payload || typeof payload !== 'object') return null;
  const obj = payload as Record<string, unknown>;
  const id = nullableNumber(obj.id);
  if (id === null) return null;

  const rows: ExamAnalysisRow[] = [];
  if (Array.isArray(obj.rows)) {
    for (const raw of obj.rows) {
      if (!raw || typeof raw !== 'object') continue;
      const r = raw as Record<string, unknown>;
      rows.push({
        subjectName: typeof r.subjectName === 'string' ? r.subjectName : '',
        wrongCount: nullableNumber(r.wrongCount) ?? 0,
        skippedCount: nullableNumber(r.skippedCount) ?? 0,
        doubtfulTotal: nullableNumber(r.doubtfulTotal) ?? 0,
        doubtfulWrong: nullableNumber(r.doubtfulWrong) ?? 0,
        doubtfulSkipped: nullableNumber(r.doubtfulSkipped) ?? 0,
        doubtfulCorrect: nullableNumber(r.doubtfulCorrect) ?? 0,
        causeNote: typeof r.causeNote === 'string' ? r.causeNote : '',
      });
    }
  }

  const notes: ExamAnalysisNote[] = [];
  if (Array.isArray(obj.notes)) {
    for (const raw of obj.notes) {
      if (!raw || typeof raw !== 'object') continue;
      const n = raw as Record<string, unknown>;
      notes.push({
        questionNumber: nullableNumber(n.questionNumber) ?? 0,
        subjectName: typeof n.subjectName === 'string' ? n.subjectName : '',
        note: typeof n.note === 'string' ? n.note : '',
      });
    }
  }

  return {
    id,
    examNumber: nullableNumber(obj.examNumber),
    examDate: nullableString(obj.examDate),
    gradeBand: nullableEnum(obj.gradeBand, EXAM_GRADE_BANDS),
    totalTara: nullableNumber(obj.totalTara),
    nationalRank: nullableNumber(obj.nationalRank),
    regionRank: nullableNumber(obj.regionRank),
    cityRank: nullableNumber(obj.cityRank),
    highestPercent: nullableNumber(obj.highestPercent),
    lowestPercent: nullableNumber(obj.lowestPercent),
    taraDelta: nullableNumber(obj.taraDelta),
    advisorReport: typeof obj.advisorReport === 'string' ? obj.advisorReport : '',
    rows,
    notes,
  };
}

function normalizeExamAnalysisList(payload: unknown): ExamAnalysis[] {
  if (!Array.isArray(payload)) return [];
  const list: ExamAnalysis[] = [];
  for (const raw of payload) {
    const item = normalizeExamAnalysis(raw);
    if (item) list.push(item);
  }
  return list;
}

function normalizeMyExamScores(payload: unknown): MyExamScoresResponse {
  const obj =
    payload && typeof payload === 'object'
      ? (payload as Record<string, unknown>)
      : {};
  return {
    active: obj.active === true,
    scores: normalizeExamScoreList(obj.scores),
  };
}

function normalizeMyExamAnalyses(payload: unknown): MyExamAnalysesResponse {
  const obj =
    payload && typeof payload === 'object'
      ? (payload as Record<string, unknown>)
      : {};
  return {
    active: obj.active === true,
    analyses: normalizeExamAnalysisList(obj.analyses),
  };
}

/* ── Restart wave 5 normalizers ──────────────────────────────────────── */

const MONTHLY_EXECUTORS: readonly MonthlyOutlookExecutor[] = [
  'ADVISOR',
  'STUDENT',
];

const CHALLENGE_STATUSES: readonly ChallengeStatus[] = [
  'ACTIVE',
  'DONE',
  'CANCELLED',
];

function normalizeMonthlyOutlook(payload: unknown): MonthlyOutlook {
  const obj =
    payload && typeof payload === 'object'
      ? (payload as Record<string, unknown>)
      : {};
  const entries: MonthlyOutlookEntry[] = [];
  if (Array.isArray(obj.entries)) {
    for (const raw of obj.entries) {
      if (!raw || typeof raw !== 'object') continue;
      const e = raw as Record<string, unknown>;
      entries.push({
        date: typeof e.date === 'string' ? e.date : '',
        event: typeof e.event === 'string' ? e.event : '',
        academicNote: typeof e.academicNote === 'string' ? e.academicNote : '',
        tasks: typeof e.tasks === 'string' ? e.tasks : '',
      });
    }
  }
  const strategies: MonthlyStrategy[] = [];
  if (Array.isArray(obj.strategies)) {
    for (const raw of obj.strategies) {
      if (!raw || typeof raw !== 'object') continue;
      const s = raw as Record<string, unknown>;
      const position = nullableNumber(s.position);
      if (position === null) continue;
      strategies.push({
        position,
        title: typeof s.title === 'string' ? s.title : '',
        executor: coerceEnum(s.executor, MONTHLY_EXECUTORS, 'STUDENT'),
        body: typeof s.body === 'string' ? s.body : '',
      });
    }
  }
  return {
    monthStart: typeof obj.monthStart === 'string' ? obj.monthStart : '',
    entries,
    strategies,
  };
}

function normalizeMyMonthlyOutlook(payload: unknown): MyMonthlyOutlookResponse {
  const obj =
    payload && typeof payload === 'object'
      ? (payload as Record<string, unknown>)
      : {};
  return {
    active: obj.active === true,
    outlook: obj.outlook == null ? null : normalizeMonthlyOutlook(obj.outlook),
  };
}

function normalizeChallengeDays(payload: unknown): ChallengeDay[] {
  const source = Array.isArray(payload)
    ? payload
    : payload && typeof payload === 'object'
      ? (payload as Record<string, unknown>).days
      : null;
  const days: ChallengeDay[] = [];
  if (!Array.isArray(source)) return days;
  for (const raw of source) {
    if (!raw || typeof raw !== 'object') continue;
    const d = raw as Record<string, unknown>;
    const dayNumber = nullableNumber(d.dayNumber);
    if (dayNumber === null) continue;
    days.push({
      dayNumber,
      goal: typeof d.goal === 'string' ? d.goal : '',
      summary: typeof d.summary === 'string' ? d.summary : '',
    });
  }
  return days;
}

function normalizeChallenge(payload: unknown): Challenge | null {
  if (!payload || typeof payload !== 'object') return null;
  const obj = payload as Record<string, unknown>;
  const id = nullableNumber(obj.id);
  if (id === null) return null;
  return {
    id,
    title: typeof obj.title === 'string' ? obj.title : '',
    goalText: typeof obj.goalText === 'string' ? obj.goalText : '',
    dailyRoutine: typeof obj.dailyRoutine === 'string' ? obj.dailyRoutine : '',
    executionNote:
      typeof obj.executionNote === 'string' ? obj.executionNote : '',
    observer: typeof obj.observer === 'string' ? obj.observer : '',
    problemTarget:
      typeof obj.problemTarget === 'string' ? obj.problemTarget : '',
    startDate: typeof obj.startDate === 'string' ? obj.startDate : '',
    endDate: typeof obj.endDate === 'string' ? obj.endDate : '',
    status: coerceEnum(obj.status, CHALLENGE_STATUSES, 'ACTIVE'),
    days: normalizeChallengeDays(obj.days),
  };
}

function normalizeChallengeList(payload: unknown): Challenge[] {
  if (!Array.isArray(payload)) return [];
  const list: Challenge[] = [];
  for (const raw of payload) {
    const item = normalizeChallenge(raw);
    if (item) list.push(item);
  }
  return list;
}

function normalizeMyChallenges(payload: unknown): MyChallengesResponse {
  const obj =
    payload && typeof payload === 'object'
      ? (payload as Record<string, unknown>)
      : {};
  return {
    active: obj.active === true,
    challenges: normalizeChallengeList(obj.challenges),
  };
}

function normalizeAdvisorOverview(payload: unknown): AdvisorOverviewResponse {
  // Defensive by default (t.find lesson): any shape drift degrades to empty
  // metrics instead of crashing the dashboard render.
  const obj =
    payload && typeof payload === 'object'
      ? (payload as Record<string, unknown>)
      : {};
  const rawMetrics =
    obj.metrics && typeof obj.metrics === 'object'
      ? (obj.metrics as Record<string, unknown>)
      : {};
  const students: AdvisorOverviewStudentRow[] = [];
  if (Array.isArray(obj.students)) {
    for (const raw of obj.students) {
      if (!raw || typeof raw !== 'object') continue;
      const s = raw as Record<string, unknown>;
      const engagementId = nullableNumber(s.engagementId);
      if (engagementId === null) continue;
      students.push({
        engagementId,
        adherence7d: nullableNumber(s.adherence7d),
        lastLogDate: nullableString(s.lastLogDate),
        activeChallengeTitle: nullableString(s.activeChallengeTitle),
      });
    }
  }
  return {
    metrics: {
      activeStudents: nullableNumber(rawMetrics.activeStudents) ?? 0,
      pendingInvites: nullableNumber(rawMetrics.pendingInvites) ?? 0,
      averageAdherence7d: nullableNumber(rawMetrics.averageAdherence7d),
    },
    students,
  };
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

export async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
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
   * Headline metrics + per-student enrichment for the advisor home cockpit,
   * keyed by ENGAGEMENT id (join to `AdvisorStudent.id` client-side). The
   * payload is normalized defensively so a partially-shaped answer degrades
   * to empty metrics instead of breaking the dashboard render.
   */
  getAdvisorOverview: async (): Promise<AdvisorOverviewResponse> => {
    const payload: unknown = await requestJson<unknown>('/advisory/overview/');
    return normalizeAdvisorOverview(payload);
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

  /* ── Restart wave 3 ──────────────────────────────────────────────────── */

  /**
   * One student's «شناخت» profile (restart step 2). The server initializes an
   * empty profile on first read, so GET always answers 200 for an owned
   * engagement; a missing/foreign engagement answers 404 like every other
   * advisor route.
   */
  getIntake: async (engagementId: number): Promise<IntakePayload> => {
    const payload: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/intake/`,
    );
    return normalizeIntakePayload(payload);
  },

  /**
   * WHOLE set-replace of the intake profile, classes included (row cap 10,
   * weekday 0..6, end>start when both set — violations answer 400 with their
   * Persian detail). Returns the stored profile so callers re-render from the
   * server's normalization, never from local guesses.
   */
  putIntake: async (
    engagementId: number,
    payload: IntakePayload,
  ): Promise<IntakePayload> => {
    const saved: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/intake/`,
      { method: 'PUT', body: JSON.stringify(payload) },
    );
    return normalizeIntakePayload(saved);
  },

  /**
   * The student-side mirror read. Quiet: no active advisor ⇒
   * `{ active: false, intake: null }`, never an error.
   */
  getMyIntake: async (): Promise<MyIntakeResponse> => {
    const payload: unknown = await requestJson<unknown>('/advisory/me/intake/');
    return normalizeMyIntake(payload);
  },

  /**
   * Student-side intake save. `409` «ابتدا مشاور خود را تأیید کنید.» when no
   * active advisor; validation errors mirror the advisor route.
   */
  putMyIntake: async (payload: IntakePayload): Promise<MyIntakeResponse> => {
    const saved: unknown = await requestJson<unknown>('/advisory/me/intake/', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    return normalizeMyIntake(saved);
  },

  /**
   * Criteria meta + saved weekly assessments (step 7), descending by weekStart.
   * Labels come from the server's canonical list — render from them, never
   * hardcode.
   */
  getWeeklyAssessments: async (
    engagementId: number,
  ): Promise<WeeklyAssessmentsResponse> => {
    const payload: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/weekly-assessments/`,
    );
    return normalizeWeeklyAssessments(payload);
  },

  /**
   * Upsert ONE week's assessment (`?week_start=` must be a Saturday — else
   * 400). All criteria must be scored 1..5 or the 400 names the missing one;
   * its Persian detail surfaces verbatim via `requestJson`. Returns the saved
   * item.
   */
  putWeeklyAssessment: async (
    engagementId: number,
    weekStart: string,
    body: SaveWeeklyAssessmentBody,
  ): Promise<WeeklyAssessmentItem | null> => {
    const saved: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/weekly-assessments/?week_start=${encodeURIComponent(weekStart)}`,
      { method: 'PUT', body: JSON.stringify(body) },
    );
    return normalizeWeeklyAssessmentItem(saved);
  },

  /**
   * The four most recent call-log weeks (step 10); absent weeks arrive filled
   * virtually with `done:false`.
   */
  getCallLogs: async (engagementId: number): Promise<CallLogsResponse> => {
    const payload: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/call-logs/`,
    );
    const obj =
      payload && typeof payload === 'object'
        ? (payload as Record<string, unknown>)
        : {};
    const weeks: CallLogItem[] = [];
    if (Array.isArray(obj.weeks)) {
      for (const raw of obj.weeks) {
        const item = normalizeCallLogItem(raw);
        if (item && item.weekStart) weeks.push(item);
      }
    }
    return { weeks };
  },

  /**
   * Upsert ONE call-log row (`?week_start=` Saturday-anchored). Fields ride
   * along explicitly every save so a cleared topic/note/date actually clears.
   * Non-Saturday week_start ⇒ 400 with its Persian detail.
   */
  putCallLog: async (
    engagementId: number,
    weekStart: string,
    body: SaveCallLogBody,
  ): Promise<CallLogItem | null> => {
    const saved: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/call-logs/?week_start=${encodeURIComponent(weekStart)}`,
      { method: 'PUT', body: JSON.stringify(body) },
    );
    return normalizeCallLogItem(saved);
  },

  /* ── Restart wave 4 ──────────────────────────────────────────────────── */

  /**
   * One student's exam scores (restart step 5), descending by exam date.
   * The roster cap (40 rows per engagement) is enforced server-side; crossing
   * it answers 400 «سقف ثبت نمرات پر شده است.» whose Persian detail surfaces
   * verbatim via `requestJson`.
   */
  getExamScores: async (engagementId: number): Promise<ExamScore[]> => {
    const payload: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/exam-scores/`,
    );
    return normalizeExamScoreList(payload);
  },

  /**
   * Create one exam score. Validation errors (percent outside 0..100, unknown
   * kind, cap reached) answer 400 with their Persian detail — surfaced
   * verbatim by `requestJson`. Returns the stored row.
   */
  createExamScore: async (
    engagementId: number,
    body: CreateExamScoreBody,
  ): Promise<ExamScore> => {
    const saved: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/exam-scores/`,
      { method: 'POST', body: JSON.stringify(body) },
    );
    const item = normalizeExamScore(saved);
    if (!item) throw new Error('پاسخ سرور برای نمرۀ ذخیره‌شده نامعتبر بود.');
    return item;
  },

  /**
   * Partially update ONE score: only the keys present in `patch` change
   * server-side; everything absent stays as stored. A missing/foreign score
   * answers 404 like every other advisor detail route.
   */
  updateExamScore: async (
    engagementId: number,
    scoreId: number,
    patch: UpdateExamScoreBody,
  ): Promise<ExamScore> => {
    const saved: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/exam-scores/${scoreId}/`,
      { method: 'PATCH', body: JSON.stringify(patch) },
    );
    const item = normalizeExamScore(saved);
    if (!item) throw new Error('پاسخ سرور برای نمرۀ ویرایش‌شده نامعتبر بود.');
    return item;
  },

  /**
   * Delete one score permanently. Terminal — there is no undo route.
   */
  deleteExamScore: async (
    engagementId: number,
    scoreId: number,
  ): Promise<void> => {
    await requestJson<unknown>(
      `/advisory/students/${engagementId}/exam-scores/${scoreId}/`,
      { method: 'DELETE' },
    );
  },

  /**
   * The student-side mirror of the exam scores. Quiet like every student
   * advisory read: no active advisor ⇒ `{ active: false, scores: [] }`.
   */
  getMyExamScores: async (): Promise<MyExamScoresResponse> => {
    const payload: unknown = await requestJson<unknown>(
      '/advisory/me/exam-scores/',
    );
    return normalizeMyExamScores(payload);
  },

  /**
   * One student's exam analyses / report cards (restart step 6), descending
   * by exam date. Rows and notes arrive embedded in each item.
   */
  getExamAnalyses: async (engagementId: number): Promise<ExamAnalysis[]> => {
    const payload: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/exam-analyses/`,
    );
    return normalizeExamAnalysisList(payload);
  },

  /**
   * Create one analysis with its rows and notes in a single transaction.
   * Duplicate question numbers inside `notes` answer 400 «شمارهٔ سؤال تکراری
   * است.»; out-of-range numbers and illogical doubtful counts answer 400 too
   * — all Persian details surface verbatim via `requestJson`.
   */
  createExamAnalysis: async (
    engagementId: number,
    body: ExamAnalysisWriteBody,
  ): Promise<ExamAnalysis> => {
    const saved: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/exam-analyses/`,
      { method: 'POST', body: JSON.stringify(body) },
    );
    const item = normalizeExamAnalysis(saved);
    if (!item) throw new Error('پاسخ سرور برای تحلیل ذخیره‌شده نامعتبر بود.');
    return item;
  },

  /**
   * WHOLE set-replace of one analysis: rows and notes ride along in full —
   * whatever the payload omits is deleted server-side. Send the entire
   * object every time, never a diff. Missing/foreign id ⇒ 404.
   */
  replaceExamAnalysis: async (
    engagementId: number,
    analysisId: number,
    body: ExamAnalysisWriteBody,
  ): Promise<ExamAnalysis> => {
    const saved: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/exam-analyses/${analysisId}/`,
      { method: 'PUT', body: JSON.stringify(body) },
    );
    const item = normalizeExamAnalysis(saved);
    if (!item) throw new Error('پاسخ سرور برای تحلیل ویرایش‌شده نامعتبر بود.');
    return item;
  },

  /**
   * Delete one analysis together with its rows and notes. Terminal.
   */
  deleteExamAnalysis: async (
    engagementId: number,
    analysisId: number,
  ): Promise<void> => {
    await requestJson<unknown>(
      `/advisory/students/${engagementId}/exam-analyses/${analysisId}/`,
      { method: 'DELETE' },
    );
  },

  /**
   * The student-side mirror of the analyses. Quiet: no active advisor ⇒
   * `{ active: false, analyses: [] }`, never an error.
   */
  getMyExamAnalyses: async (): Promise<MyExamAnalysesResponse> => {
    const payload: unknown = await requestJson<unknown>(
      '/advisory/me/exam-analyses/',
    );
    return normalizeMyExamAnalyses(payload);
  },

  /* ── Restart wave 5 ──────────────────────────────────────────────────── */

  /**
   * One month's outlook («ماه در یک نگاه», restart step 8). `monthStartIso` is
   * the GREGORIAN first day of the chosen Jalali month (client-side
   * date-fns-jalali conversion — a Jalali string must never reach the wire).
   * The first read of a never-saved month answers the empty default payload,
   * never 404.
   */
  getMonthlyOutlook: async (
    engagementId: number,
    monthStartIso: string,
  ): Promise<MonthlyOutlook> => {
    const payload: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/monthly-outlooks/${encodeURIComponent(monthStartIso)}/`,
    );
    return normalizeMonthlyOutlook(payload);
  },

  /**
   * WHOLE set-replace of one month: entries and strategies ride along in full
   * — whatever the payload omits is deleted server-side. Duplicate entry dates
   * or duplicate strategy positions answer 400 with their Persian detail,
   * surfaced verbatim by `requestJson`. Returns the stored payload.
   */
  putMonthlyOutlook: async (
    engagementId: number,
    monthStartIso: string,
    payload: MonthlyOutlook,
  ): Promise<MonthlyOutlook> => {
    const saved: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/monthly-outlooks/${encodeURIComponent(monthStartIso)}/`,
      { method: 'PUT', body: JSON.stringify(payload) },
    );
    return normalizeMonthlyOutlook(saved);
  },

  /**
   * The student-side mirror of one month's outlook. Quiet like every student
   * advisory read: no active advisor ⇒ `{ active: false, outlook: null }`.
   */
  getMyMonthlyOutlook: async (
    monthStartIso: string,
  ): Promise<MyMonthlyOutlookResponse> => {
    const payload: unknown = await requestJson<unknown>(
      `/advisory/me/monthly-outlooks/${encodeURIComponent(monthStartIso)}/`,
    );
    return normalizeMyMonthlyOutlook(payload);
  },

  /**
   * One student's challenges (restart step 9). Crossing the three-ACTIVE cap
   * on create answers 400 «حداکثر ۳ چالش فعال…» whose Persian detail surfaces
   * verbatim via `requestJson` — show it as-is, it is user-facing copy.
   */
  getChallenges: async (engagementId: number): Promise<Challenge[]> => {
    const payload: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/challenges/`,
    );
    return normalizeChallengeList(payload);
  },

  /**
   * Create one challenge. `endDate` is NEVER sent — the server derives it as
   * `startDate + 6` and returns the stored row including its days.
   */
  createChallenge: async (
    engagementId: number,
    body: CreateChallengeBody,
  ): Promise<Challenge> => {
    const saved: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/challenges/`,
      { method: 'POST', body: JSON.stringify(body) },
    );
    const item = normalizeChallenge(saved);
    if (!item) throw new Error('پاسخ سرور برای چالش ساخته‌شده نامعتبر بود.');
    return item;
  },

  /**
   * Partially update ONE challenge: metadata keys and/or `status`. Flipping a
   * terminal status back to ACTIVE answers 409 with its Persian detail.
   */
  patchChallenge: async (
    engagementId: number,
    challengeId: number,
    patch: UpdateChallengeBody,
  ): Promise<Challenge> => {
    const saved: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/challenges/${challengeId}/`,
      { method: 'PATCH', body: JSON.stringify(patch) },
    );
    const item = normalizeChallenge(saved);
    if (!item) throw new Error('پاسخ سرور برای چالش ویرایش‌شده نامعتبر بود.');
    return item;
  },

  /**
   * Delete one challenge together with its days. Terminal — there is no undo.
   */
  deleteChallenge: async (
    engagementId: number,
    challengeId: number,
  ): Promise<void> => {
    await requestJson<unknown>(
      `/advisory/students/${engagementId}/challenges/${challengeId}/`,
      { method: 'DELETE' },
    );
  },

  /**
   * WHOLE set-replace of one challenge's 7 days (advisor side — every field
   * writable). `dayNumber` outside 1..7 answers 400 with its Persian detail.
   * Returns the stored days; when the response shape is not recognizable the
   * sent rows are echoed back so callers can keep rendering.
   */
  putAdvisorDays: async (
    engagementId: number,
    challengeId: number,
    days: SaveChallengeDaysBody,
  ): Promise<ChallengeDay[]> => {
    const saved: unknown = await requestJson<unknown>(
      `/advisory/students/${engagementId}/challenges/${challengeId}/days/`,
      { method: 'PUT', body: JSON.stringify({ days }) },
    );
    const normalized = normalizeChallengeDays(saved);
    return normalized.length > 0 ? normalized : days;
  },

  /**
   * The student-side mirror of the challenges. Quiet: no active advisor ⇒
   * `{ active: false, challenges: [] }`, never an error.
   */
  getMyChallenges: async (): Promise<MyChallengesResponse> => {
    const payload: unknown = await requestJson<unknown>(
      '/advisory/me/challenges/',
    );
    return normalizeMyChallenges(payload);
  },

  /**
   * The student-side day writer: ONLY goal/summary are accepted (any other
   * field ⇒ 400 «فقط هدف و خلاصهٔ روز را می‌توانید ثبت کنید.»); writing a day
   * whose date has not arrived yet answers 400. Persian details surface
   * verbatim via `requestJson`. Returns the stored days (sent rows echoed on
   * an unrecognizable response shape, same posture as `putAdvisorDays`).
   */
  putMyChallengeDays: async (
    challengeId: number,
    days: StudentChallengeDayBody[],
  ): Promise<ChallengeDay[]> => {
    const saved: unknown = await requestJson<unknown>(
      `/advisory/me/challenges/${challengeId}/days/`,
      { method: 'PUT', body: JSON.stringify({ days }) },
    );
    const normalized = normalizeChallengeDays(saved);
    return normalized.length > 0 ? normalized : days;
  },
};
