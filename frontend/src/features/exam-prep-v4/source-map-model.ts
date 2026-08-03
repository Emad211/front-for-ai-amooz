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
  displayOrder: number;
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
  displayOrder: number;
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

export function sortEditablePagesByDisplayOrder(
  pages: readonly EditableSourceMapPage[],
): EditableSourceMapPage[] {
  return [...pages]
    .map((page) => ({ ...page }))
    .sort((first, second) => (
      first.displayOrder - second.displayOrder
      || first.pageNumber - second.pageNumber
    ));
}

function sortEditablePagesByPhysicalNumber(
  pages: readonly EditableSourceMapPage[],
): EditableSourceMapPage[] {
  return [...pages]
    .map((page) => ({ ...page }))
    .sort((first, second) => first.pageNumber - second.pageNumber);
}

export function createEditableSourceMapPages(
  pages: readonly ExamPrepV4Page[],
): EditableSourceMapPage[] {
  return [...pages]
    .map((page) => ({
      pageNumber: page.pageNumber,
      displayOrder: page.displayOrder,
      role: page.effectiveRole,
      orientation: page.orientation,
    }))
    .sort((first, second) => (
      first.displayOrder - second.displayOrder
      || first.pageNumber - second.pageNumber
    ));
}

export function normalizeEditableSourceMapPages(
  pages: readonly EditableSourceMapPage[],
): EditableSourceMapPage[] {
  return sortEditablePagesByDisplayOrder(pages);
}

export function isCompleteEditableSourceMap(
  pages: readonly EditableSourceMapPage[],
  pageCount: number,
): boolean {
  if (!Number.isInteger(pageCount) || pageCount < 1 || pages.length !== pageCount) {
    return false;
  }

  const expected = Array.from({ length: pageCount }, (_, index) => index + 1);
  const pageNumbers = [...pages].map((page) => page.pageNumber).sort((a, b) => a - b);
  const displayOrders = [...pages].map((page) => page.displayOrder).sort((a, b) => a - b);

  return (
    pageNumbers.every((number, index) => number === expected[index])
    && displayOrders.every((number, index) => number === expected[index])
    && pages.every((page) => (
      EXAM_PREP_V4_SOURCE_ROLES.includes(page.role)
      && VALID_ORIENTATIONS.includes(page.orientation)
    ))
  );
}

export function sourceMapPagesEqual(
  first: readonly EditableSourceMapPage[],
  second: readonly EditableSourceMapPage[],
): boolean {
  if (first.length !== second.length) return false;
  const normalizedFirst = sortEditablePagesByPhysicalNumber(first);
  const normalizedSecond = sortEditablePagesByPhysicalNumber(second);

  return normalizedFirst.every((page, index) => {
    const other = normalizedSecond[index];
    return (
      page.pageNumber === other.pageNumber
      && page.displayOrder === other.displayOrder
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

function moveEditablePage(
  pages: readonly EditableSourceMapPage[],
  pageNumber: number,
  offset: -1 | 1,
): EditableSourceMapPage[] {
  const ordered = sortEditablePagesByDisplayOrder(pages);
  const currentIndex = ordered.findIndex((page) => page.pageNumber === pageNumber);
  if (currentIndex < 0) return ordered;
  const targetIndex = currentIndex + offset;
  if (targetIndex < 0 || targetIndex >= ordered.length) return ordered;

  const current = ordered[currentIndex];
  const target = ordered[targetIndex];
  return ordered.map((page) => {
    if (page.pageNumber === current.pageNumber) {
      return { ...page, displayOrder: target.displayOrder };
    }
    if (page.pageNumber === target.pageNumber) {
      return { ...page, displayOrder: current.displayOrder };
    }
    return page;
  }).sort((first, second) => first.displayOrder - second.displayOrder);
}

export function moveEditablePageEarlier(
  pages: readonly EditableSourceMapPage[],
  pageNumber: number,
): EditableSourceMapPage[] {
  return moveEditablePage(pages, pageNumber, -1);
}

export function moveEditablePageLater(
  pages: readonly EditableSourceMapPage[],
  pageNumber: number,
): EditableSourceMapPage[] {
  return moveEditablePage(pages, pageNumber, 1);
}

export function canMoveEditablePageEarlier(
  pages: readonly EditableSourceMapPage[],
  pageNumber: number,
): boolean {
  return sortEditablePagesByDisplayOrder(pages)[0]?.pageNumber !== pageNumber;
}

export function canMoveEditablePageLater(
  pages: readonly EditableSourceMapPage[],
  pageNumber: number,
): boolean {
  const ordered = sortEditablePagesByDisplayOrder(pages);
  return ordered.at(-1)?.pageNumber !== pageNumber;
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
