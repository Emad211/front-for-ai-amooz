export type AssessmentDraftStorage = {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
};

type StoredAssessmentDraft = {
  schemaVersion: 1;
  assessmentVersion: string;
  answers: Record<string, string>;
};

function removeStoredDraft(storage: AssessmentDraftStorage, key: string): void {
  try {
    storage.removeItem(key);
  } catch {
    // Storage cleanup is best-effort and must never block assessment actions.
  }
}

export function getAssessmentDraftStorage(): AssessmentDraftStorage | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function createAssessmentDraftKey({
  ownerId,
  courseId,
  assessmentType,
  chapterId,
}: {
  ownerId: string;
  courseId: string;
  assessmentType: 'chapter-quiz' | 'final-exam';
  chapterId?: string;
}): string {
  const scope = [ownerId, courseId, assessmentType, chapterId ?? 'course']
    .map((value) => encodeURIComponent(String(value).trim()))
    .join(':');
  return `ai_amooz_assessment_draft:v1:${scope}`;
}

export function createAssessmentVersion(
  assessmentId: string | number,
  questionIds: Array<string | number>,
): string {
  return JSON.stringify([
    String(assessmentId),
    questionIds.map((questionId) => String(questionId)),
  ]);
}

export function loadAssessmentDraft(
  storage: AssessmentDraftStorage | null,
  key: string,
  assessmentVersion: string,
  questionIds: Array<string | number>,
): Record<string, string> | null {
  if (!storage || !key || !assessmentVersion) return null;

  try {
    const raw = storage.getItem(key);
    if (!raw) return null;

    const parsed = JSON.parse(raw) as Partial<StoredAssessmentDraft>;
    if (
      parsed.schemaVersion !== 1 ||
      parsed.assessmentVersion !== assessmentVersion ||
      !parsed.answers ||
      typeof parsed.answers !== 'object' ||
      Array.isArray(parsed.answers)
    ) {
      removeStoredDraft(storage, key);
      return null;
    }

    const allowedIds = new Set(questionIds.map((questionId) => String(questionId)));
    const restored = Object.fromEntries(
      Object.entries(parsed.answers).filter(
        ([questionId, answer]) => allowedIds.has(questionId) && typeof answer === 'string',
      ),
    );
    return Object.keys(restored).length ? restored : null;
  } catch {
    removeStoredDraft(storage, key);
    return null;
  }
}

export function saveAssessmentDraft(
  storage: AssessmentDraftStorage | null,
  key: string,
  assessmentVersion: string,
  answers: Record<string, string>,
): void {
  if (!storage || !key || !assessmentVersion) return;

  try {
    const answered = Object.fromEntries(
      Object.entries(answers).filter(([, answer]) => typeof answer === 'string' && answer.length > 0),
    );
    if (!Object.keys(answered).length) {
      removeStoredDraft(storage, key);
      return;
    }

    const draft: StoredAssessmentDraft = {
      schemaVersion: 1,
      assessmentVersion,
      answers: answered,
    };
    storage.setItem(key, JSON.stringify(draft));
  } catch {
    // Storage can be unavailable or full; answering the assessment must continue.
  }
}

export function clearAssessmentDraft(
  storage: AssessmentDraftStorage | null,
  key: string,
): void {
  if (!storage || !key) return;
  removeStoredDraft(storage, key);
}
