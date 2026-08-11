import type {
  ExamPrepExtractionIssue,
  ExamPrepQuestion,
  ExamPrepSessionDetail,
} from '@/services/classes-service';

export type ExamReviewSeverity = 'critical' | 'warning';

export interface ExamQuestionReviewIssue {
  code: string;
  label: string;
  description: string;
  severity: ExamReviewSeverity;
  sourcePages: number[];
}

export interface ExamQuestionReviewState {
  questionId: string;
  questionNumber: string;
  issues: ExamQuestionReviewIssue[];
  criticalCount: number;
  warningCount: number;
  needsReview: boolean;
}

export interface ExamReviewSummary {
  questions: ExamQuestionReviewState[];
  byQuestionId: Record<string, ExamQuestionReviewState>;
  globalIssues: ExamQuestionReviewIssue[];
  reviewQuestionIds: string[];
  criticalQuestionCount: number;
  warningQuestionCount: number;
}

const DIGIT_TRANSLATION: Record<string, string> = {
  '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
  '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
  '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
  '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
};

export const CRITICAL_EXAM_REVIEW_CODES = new Set([
  'no_questions',
  'missing_question_id',
  'duplicate_question_id',
  'duplicate_question_number',
  'missing_question_text',
  'missing_options',
  'missing_option_text',
  'missing_options_text',
  'missing_solution_text',
  'placeholder_option_text',
  'unexpected_option_count',
  'duplicate_option_label',
  'missing_answer',
  'missing_correct_option_label',
  'missing_previous_continuation',
  'missing_next_continuation',
  'conflicting_correct_option',
  'conflicting_correct_option_text',
  'correct_option_not_in_options',
  'missing_question_number',
  'visual_evidence_required',
  'visual_attachment_missing',
  'visual_attachment_incomplete',
  'broken_persian_text',
  'duplicate_mixed_text',
  'solution_semantic_mismatch_candidate',
  'duplicate_solution_across_questions',
  'serialized_option_payload',
  'targeted_repair_unresolved',
  'targeted_repair_failed',
  'targeted_repair_no_source_page',
  'source_verification_failed',
  'table_incomplete',
  'count_answer_unresolved',
  'stage5_finalization_blocked',
  'failed_chunk',
]);

const ISSUE_COPY: Record<string, { label: string; description: string }> = {
  no_questions: {
    label: 'هیچ سؤالی استخراج نشده',
    description: 'خروجی آزمون فاقد سؤال قابل استفاده است.',
  },
  missing_question_id: {
    label: 'شناسه سؤال وجود ندارد',
    description: 'برای این سؤال شناسه پایدار ثبت نشده است.',
  },
  duplicate_question_id: {
    label: 'شناسه سؤال تکراری است',
    description: 'دو یا چند سؤال شناسه یکسان دارند.',
  },
  duplicate_question_number: {
    label: 'شماره سؤال تکراری است',
    description: 'شماره این سؤال با سؤال دیگری تداخل دارد.',
  },
  missing_question_number: {
    label: 'شماره سؤال جا افتاده است',
    description: 'توالی شماره سؤال‌ها کامل نیست.',
  },
  missing_question_text: {
    label: 'صورت سؤال ناقص است',
    description: 'متن اصلی سؤال خالی یا قابل استفاده نیست.',
  },
  missing_options: {
    label: 'گزینه‌ها ناقص‌اند',
    description: 'برای سؤال چندگزینه‌ای گزینه کافی ثبت نشده است.',
  },
  missing_option_text: {
    label: 'متن یک یا چند گزینه خالی است',
    description: 'همه گزینه‌ها باید متن قابل خواندن داشته باشند.',
  },
  missing_options_text: {
    label: 'متن گزینه‌ها پیدا نشده',
    description: 'متن کامل گزینه‌ها از منبع استخراج نشده است.',
  },
  placeholder_option_text: {
    label: 'گزینه‌ها فقط عدد یا نشانه‌اند',
    description: 'متن واقعی گزینه‌ها را از روی منبع بررسی و وارد کنید.',
  },
  unexpected_option_count: {
    label: 'تعداد گزینه‌ها غیرعادی است',
    description: 'تعداد گزینه‌ها با ساختار معمول سؤال سازگار نیست.',
  },
  duplicate_option_label: {
    label: 'برچسب گزینه تکراری است',
    description: 'دو گزینه برچسب یکسان دارند.',
  },
  missing_answer: {
    label: 'پاسخ سؤال مشخص نیست',
    description: 'کلید پاسخ یا جواب نهایی ثبت نشده است.',
  },
  missing_correct_option_label: {
    label: 'گزینه صحیح مشخص نیست',
    description: 'برای نمره‌دهی باید گزینه صحیح انتخاب شود.',
  },
  correct_option_not_in_options: {
    label: 'گزینه صحیح در فهرست گزینه‌ها نیست',
    description: 'کلید پاسخ با برچسب گزینه‌های موجود تطابق ندارد.',
  },
  conflicting_correct_option: {
    label: 'کلیدهای پاسخ متناقض‌اند',
    description: 'منابع مختلف گزینه صحیح متفاوتی نشان می‌دهند.',
  },
  conflicting_correct_option_text: {
    label: 'متن پاسخ صحیح متناقض است',
    description: 'متن پاسخ صحیح با گزینه انتخاب‌شده تطابق ندارد.',
  },
  missing_solution_text: {
    label: 'راه‌حل تشریحی ناقص است',
    description: 'راه‌حل مورد انتظار خالی یا بسیار کوتاه است.',
  },
  solution_semantic_mismatch_candidate: {
    label: 'راه‌حل احتمالاً متعلق به این سؤال نیست',
    description: 'محتوای راه‌حل با صورت سؤال و گزینه‌ها هم‌خوانی کافی ندارد.',
  },
  duplicate_solution_across_questions: {
    label: 'راه‌حل با سؤال دیگری تکراری است',
    description: 'احتمال دارد راه‌حل سؤال دیگری به این سؤال متصل شده باشد.',
  },
  missing_previous_continuation: {
    label: 'ابتدای سؤال جا افتاده است',
    description: 'این سؤال احتمالاً ادامه صفحه قبل است و بخش ابتدایی آن موجود نیست.',
  },
  missing_next_continuation: {
    label: 'انتهای سؤال جا افتاده است',
    description: 'ادامه سؤال در صفحه بعد به این رکورد متصل نشده است.',
  },
  visual_evidence_required: {
    label: 'تصویر یا نمودار باید بررسی شود',
    description: 'پاسخ‌گویی به این سؤال به شکل، جدول یا نمودار منبع وابسته است.',
  },
  visual_attachment_missing: {
    label: 'تصویر لازم متصل نشده است',
    description: 'تصویر موردنیاز سؤال در خروجی وجود ندارد.',
  },
  visual_attachment_incomplete: {
    label: 'تصویر سؤال کامل نیست',
    description: 'همه بخش‌های لازم شکل یا گزینه‌های تصویری داخل تصویر نیستند.',
  },
  table_incomplete: {
    label: 'جدول ناقص است',
    description: 'ردیف‌ها یا ستون‌های لازم جدول کامل استخراج نشده‌اند.',
  },
  count_answer_unresolved: {
    label: 'پاسخ سؤال شمارشی قطعی نیست',
    description: 'تعداد مورد صحیح یا گزینه نهایی نیاز به بررسی دستی دارد.',
  },
  broken_persian_text: {
    label: 'متن فارسی خراب است',
    description: 'بخشی از متن به‌هم‌ریخته یا ناخوانا استخراج شده است.',
  },
  duplicate_mixed_text: {
    label: 'متن سالم و خراب هم‌زمان تکرار شده',
    description: 'نسخه‌های تکراری و ناسازگار یک متن داخل سؤال دیده می‌شود.',
  },
  serialized_option_payload: {
    label: 'گزینه به‌صورت داده خام ذخیره شده',
    description: 'متن گزینه باید از ساختار JSON خام جدا و اصلاح شود.',
  },
  source_verification_failed: {
    label: 'تطبیق با منبع قطعی نشده',
    description: 'سیستم نتوانسته صحت سؤال یا پاسخ را از روی صفحه منبع تأیید کند؛ دستی بررسی کنید.',
  },
  stage5_finalization_blocked: {
    label: 'تأیید نهایی این بخش قطعی نشده است',
    description: 'تأیید نهایی منبع کامل نشده است؛ صفحه منبع را بررسی و سپس این مورد را تأیید کنید.',
  },
  targeted_repair_unresolved: {
    label: 'اصلاح خودکار کامل نشده',
    description: 'پس از بررسی خودکار هنوز مشکل سؤال باقی مانده است.',
  },
  targeted_repair_failed: {
    label: 'اصلاح خودکار شکست خورده',
    description: 'درخواست اصلاح سؤال نتیجه قابل اعتماد نداده است.',
  },
  targeted_repair_no_source_page: {
    label: 'صفحه منبع سؤال پیدا نشده',
    description: 'برای تطبیق سؤال، صفحه منبع قابل استفاده در دسترس نبوده است.',
  },
  failed_chunk: {
    label: 'یک صفحه پردازش نشده است',
    description: 'این مورد به یک صفحه کامل مربوط است و ممکن است با یک سؤال خاص قابل تطبیق نباشد.',
  },
  out_of_scope_answer: {
    label: 'پاسخ بدون سؤال متناظر',
    description: 'یک پاسخ اضافی در منبع وجود دارد که به سؤال موجودی متصل نشده است.',
  },
};

function latinDigits(value: unknown): string {
  return String(value ?? '')
    .split('')
    .map((char) => DIGIT_TRANSLATION[char] ?? char)
    .join('');
}

export function normalizeExamQuestionNumber(value: unknown): string {
  const match = latinDigits(value).match(/\d+/);
  return match ? String(Number(match[0])) : '';
}

function normalizeSection(value: unknown): string {
  return String(value ?? '').trim().toLocaleLowerCase('en-US').replace(/\s+/g, ' ');
}

function sourcePages(values: unknown): number[] {
  if (!Array.isArray(values)) return [];
  const pages: number[] = [];
  for (const value of values) {
    const page = Number(value);
    if (Number.isInteger(page) && page > 0 && !pages.includes(page)) pages.push(page);
  }
  return pages.sort((a, b) => a - b);
}

function questionNumber(question: ExamPrepQuestion, index: number): string {
  return normalizeExamQuestionNumber(
    question.source_question_number ?? question.question_number ?? index + 1,
  ) || String(index + 1);
}

function issueMatchesQuestion(
  issue: ExamPrepExtractionIssue,
  question: ExamPrepQuestion,
  index: number,
): boolean {
  const number = questionNumber(question, index);
  const section = normalizeSection(question.section_key);
  const keyCandidates = new Set([
    question.question_id,
    `${section}::${number}`,
    `default::${number}`,
    `::${number}`,
  ]);
  if (issue.questionKey && keyCandidates.has(String(issue.questionKey))) return true;

  const issueNumber = normalizeExamQuestionNumber(
    issue.sourceQuestionNumber ?? issue.questionNumber,
  );
  return Boolean(issueNumber && issueNumber === number);
}

export function describeExamReviewIssue(
  issue: Pick<ExamPrepExtractionIssue, 'code' | 'severity' | 'sourcePages'>,
): ExamQuestionReviewIssue {
  const code = String(issue.code || 'unknown_issue').trim() || 'unknown_issue';
  const copy = ISSUE_COPY[code] ?? {
    label: 'نیازمند بررسی دستی',
    description: `کد فنی: ${code}`,
  };
  return {
    code,
    label: copy.label,
    description: copy.description,
    severity:
      issue.severity === 'critical'
      || CRITICAL_EXAM_REVIEW_CODES.has(code)
      || code.startsWith('conflicting_option:')
        ? 'critical'
        : 'warning',
    sourcePages: sourcePages(issue.sourcePages),
  };
}

export function buildExamReviewSummary(
  detail: Pick<ExamPrepSessionDetail, 'exam_prep_data' | 'extractionAudit'>,
): ExamReviewSummary {
  const questions = detail.exam_prep_data?.exam_prep?.questions ?? [];
  const auditIssues = detail.extractionAudit?.issues ?? [];
  const matchedAuditIndexes = new Set<number>();
  const states = questions.map((question, index): ExamQuestionReviewState => {
    const reviewedCodes = new Set(question.teacher_reviewed_issue_codes ?? []);
    const combined = new Map<string, ExamQuestionReviewIssue>();

    for (const code of question.issues ?? []) {
      if (reviewedCodes.has(code)) continue;
      combined.set(code, describeExamReviewIssue({ code, severity: 'warning', sourcePages: question.source_pages }));
    }

    auditIssues.forEach((issue, issueIndex) => {
      if (!issueMatchesQuestion(issue, question, index)) return;
      matchedAuditIndexes.add(issueIndex);
      if (reviewedCodes.has(issue.code)) return;
      const described = describeExamReviewIssue(issue);
      const previous = combined.get(described.code);
      combined.set(described.code, previous?.severity === 'critical' ? previous : described);
    });

    const issues = Array.from(combined.values()).sort((left, right) => {
      if (left.severity !== right.severity) return left.severity === 'critical' ? -1 : 1;
      return left.label.localeCompare(right.label, 'fa');
    });
    const criticalCount = issues.filter((issue) => issue.severity === 'critical').length;
    const warningCount = issues.length - criticalCount;
    return {
      questionId: question.question_id || `q-${index + 1}`,
      questionNumber: questionNumber(question, index),
      issues,
      criticalCount,
      warningCount,
      needsReview: issues.length > 0,
    };
  });

  const globalIssues = auditIssues
    .filter((_issue, index) => !matchedAuditIndexes.has(index))
    .map(describeExamReviewIssue);
  const byQuestionId = Object.fromEntries(states.map((state) => [state.questionId, state]));
  const reviewQuestionIds = states.filter((state) => state.needsReview).map((state) => state.questionId);

  return {
    questions: states,
    byQuestionId,
    globalIssues,
    reviewQuestionIds,
    criticalQuestionCount: states.filter((state) => state.criticalCount > 0).length,
    warningQuestionCount: states.filter(
      (state) => state.criticalCount === 0 && state.warningCount > 0,
    ).length,
  };
}
