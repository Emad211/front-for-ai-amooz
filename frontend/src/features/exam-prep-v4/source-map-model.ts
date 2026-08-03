export const EXAM_PREP_V4_SOURCE_ROLES = [
  'cover',
  'questions',
  'answer_solutions',
  'answer_key',
  'inline_question_answer',
  'ignored',
  'unknown',
] as const;

export type ExamPrepV4SourceRole = (typeof EXAM_PREP_V4_SOURCE_ROLES)[number];
export type ExamPrepV4Orientation = 0 | 90 | 180 | 270;

export type ExamPrepV4Page = {
  pageNumber: number;
  predictedRole: ExamPrepV4SourceRole;
  predictedConfidence: number;
  teacherRole: ExamPrepV4SourceRole | null;
  effectiveRole: ExamPrepV4SourceRole;
  orientation: ExamPrepV4Orientation;
  width: number;
  height: number;
  hasThumbnail: boolean;
  isDuplicate: boolean;
};

export type EditableSourceMapPage = {
  pageNumber: number;
  role: ExamPrepV4SourceRole;
  orientation: ExamPrepV4Orientation;
};

export const SOURCE_ROLE_LABELS: Record<ExamPrepV4SourceRole, string> = {
  cover: 'جلد و راهنما',
  questions: 'سؤال‌ها',
  answer_solutions: 'پاسخ و راه‌حل تشریحی',
  answer_key: 'کلید پاسخ',
  inline_question_answer: 'سؤال با پاسخ کنار آن',
  ignored: 'نادیده گرفته شود',
  unknown: 'نامشخص',
};

export const SOURCE_ROLE_SHORT_LABELS: Record<ExamPrepV4SourceRole, string> = {
  cover: 'جلد',
  questions: 'سؤال',
  answer_solutions: 'پاسخ تشریحی',
  answer_key: 'کلید',
  inline_question_answer: 'سؤال‌ـپاسخ',
  ignored: 'نادیده',
  unknown: 'نامشخص',
};

export const SOURCE_ROLE_DESCRIPTIONS: Record<ExamPrepV4SourceRole, string> = {
  cover: 'صفحهٔ عنوان، مشخصات یا دستورالعمل آزمون',
  questions: 'صفحه‌ای که سؤال‌ها را بدون پاسخ تشریحی منبع نشان می‌دهد',
  answer_solutions: 'پاسخ درست همراه با توضیح یا حل تشریحی',
  answer_key: 'فهرست یا جدول کوتاه پاسخ‌ها بدون توضیح مفصل',
  inline_question_answer: 'پاسخ یا راه‌حل مستقیماً کنار همان سؤال قرار دارد',
  ignored: 'تبلیغ، صفحهٔ سفید یا محتوای خارج از آزمون',
  unknown: 'نقش صفحه هنوز قطعی نیست و باید تعیین شود',
};

const VALID_ORIENTATIONS: readonly ExamPrepV4Orientation[] = [0, 90, 180, 270];

export function createEditableSourceMapPages(
  pages: readonly ExamPrepV4Page[],
): EditableSourceMapPage[] {
  return [...pages]
    .sort((first, second) => first.pageNumber - second.pageNumber)
    .map((page) => ({
      pageNumber: page.pageNumber,
      role: page.effectiveRole,
      orientation: page.orientation,
    }));
}

export function normalizeEditableSourceMapPages(
  pages: readonly EditableSourceMapPage[],
): EditableSourceMapPage[] {
  return [...pages]
    .map((page) => ({
      pageNumber: page.pageNumber,
      role: page.role,
      orientation: page.orientation,
    }))
    .sort((first, second) => first.pageNumber - second.pageNumber);
}

export function isCompleteEditableSourceMap(
  pages: readonly EditableSourceMapPage[],
  pageCount: number,
): boolean {
  if (!Number.isInteger(pageCount) || pageCount < 1 || pages.length !== pageCount) {
    return false;
  }

  const normalized = normalizeEditableSourceMapPages(pages);
  return normalized.every((page, index) => {
    return (
      page.pageNumber === index + 1
      && EXAM_PREP_V4_SOURCE_ROLES.includes(page.role)
      && VALID_ORIENTATIONS.includes(page.orientation)
    );
  });
}

export function sourceMapPagesEqual(
  first: readonly EditableSourceMapPage[],
  second: readonly EditableSourceMapPage[],
): boolean {
  if (first.length !== second.length) return false;
  const normalizedFirst = normalizeEditableSourceMapPages(first);
  const normalizedSecond = normalizeEditableSourceMapPages(second);

  return normalizedFirst.every((page, index) => {
    const other = normalizedSecond[index];
    return (
      page.pageNumber === other.pageNumber
      && page.role === other.role
      && page.orientation === other.orientation
    );
  });
}

export function updateEditablePageRole(
  pages: readonly EditableSourceMapPage[],
  pageNumber: number,
  role: ExamPrepV4SourceRole,
): EditableSourceMapPage[] {
  return pages.map((page) => (
    page.pageNumber === pageNumber ? { ...page, role } : page
  ));
}

export function rotateEditablePageClockwise(
  pages: readonly EditableSourceMapPage[],
  pageNumber: number,
): EditableSourceMapPage[] {
  return pages.map((page) => {
    if (page.pageNumber !== pageNumber) return page;
    const orientation = ((page.orientation + 90) % 360) as ExamPrepV4Orientation;
    return { ...page, orientation };
  });
}

export function countUnknownPages(
  pages: readonly EditableSourceMapPage[],
): number {
  return pages.filter((page) => page.role === 'unknown').length;
}

export function canConfirmEditableSourceMap({
  pages,
  initialPages,
  pageCount,
  fingerprint,
  isSaving,
  isConfirming,
  isConfirmed,
}: {
  pages: readonly EditableSourceMapPage[];
  initialPages: readonly EditableSourceMapPage[];
  pageCount: number;
  fingerprint: string;
  isSaving: boolean;
  isConfirming: boolean;
  isConfirmed: boolean;
}): boolean {
  return (
    isCompleteEditableSourceMap(pages, pageCount)
    && sourceMapPagesEqual(pages, initialPages)
    && countUnknownPages(pages) === 0
    && /^[a-f0-9]{64}$/.test(fingerprint)
    && !isSaving
    && !isConfirming
    && !isConfirmed
  );
}

export function buildSourceMapMutationPayload(
  expectedRevision: number,
  pages: readonly EditableSourceMapPage[],
): {
  expectedRevision: number;
  pages: EditableSourceMapPage[];
} {
  return {
    expectedRevision,
    pages: normalizeEditableSourceMapPages(pages),
  };
}

export function roleConfidencePercent(confidence: number): number {
  if (!Number.isFinite(confidence)) return 0;
  return Math.min(100, Math.max(0, Math.round(confidence * 100)));
}
