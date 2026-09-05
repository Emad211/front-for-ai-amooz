'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  HelpCircle,
  ListFilter,
  Loader2,
  Plus,
  Save,
  ShieldCheck,
  Trash2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { CLASS_TITLE_MAX_LENGTH } from '@/constants/teacher-limits';
import type {
  ExamPrepSessionDetail,
  ExamPrepData,
  ExamPrepQuestion,
  ExamPrepSessionUpdatePayload,
  ExamPrepTeacherVisual,
} from '@/services/classes-service';
import { visualMatchesOption, visualsForRole } from '@/lib/exam-visuals';
import { QuestionVisualUploader, TeacherVisualCard } from './question-visual-tools';
import {
  buildExamReviewSummary,
  type ExamQuestionReviewState,
} from './exam-review-utils';

interface ExamEditFormProps {
  examDetail: ExamPrepSessionDetail;
  onSave: (data: ExamPrepSessionUpdatePayload) => Promise<void>;
  isSaving?: boolean;
}

type ReviewFilter = 'all' | 'needs_review';

const levelOptions = [
  { value: 'مبتدی', label: 'مبتدی' },
  { value: 'متوسط', label: 'متوسط' },
  { value: 'پیشرفته', label: 'پیشرفته' },
];

const STANDARD_OPTION_LABELS = ['1', '2', '3', '4'] as const;

function editableOptionLabels(options: readonly { label: string }[]): string[] {
  const labels: string[] = [...STANDARD_OPTION_LABELS];
  for (const option of options) {
    if (!labels.includes(option.label)) {
      labels.push(option.label);
    }
  }
  return labels;
}

function initialExamData(examDetail: ExamPrepSessionDetail): ExamPrepData {
  return examDetail.exam_prep_data || {
    exam_prep: { title: examDetail.title, questions: [] },
  };
}

function questionValue(question: ExamPrepQuestion, index: number): string {
  return question.question_id || `q-${index + 1}`;
}

/**
 * V4 questions are projections of the reviewed source records.  The legacy
 * editor can still update session metadata, but must not let a teacher edit
 * the projected question payload (doing so would break the source mapping).
 */
function isSourceAwareQuestion(question: ExamPrepQuestion): boolean {
  return String(question.question_id || '').startsWith('v4-');
}

export function ExamEditForm({ examDetail, onSave, isSaving }: ExamEditFormProps) {
  const [formData, setFormData] = useState({
    title: examDetail.title,
    description: examDetail.description,
    level: examDetail.level || 'مبتدی' as const,
    duration: examDetail.duration || '',
  });
  const [examData, setExamData] = useState<ExamPrepData>(() => initialExamData(examDetail));
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>('all');
  const [openQuestionIds, setOpenQuestionIds] = useState<string[]>([]);
  const [isUploadingVisual, setIsUploadingVisual] = useState(false);
  const questionRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const reviewSummary = useMemo(
    () => buildExamReviewSummary({
      exam_prep_data: examData,
      extractionAudit: examDetail.extractionAudit,
    }),
    [examData, examDetail.extractionAudit],
  );

  useEffect(() => {
    const nextExamData = initialExamData(examDetail);
    const nextSummary = buildExamReviewSummary({
      exam_prep_data: nextExamData,
      extractionAudit: examDetail.extractionAudit,
    });
    setFormData({
      title: examDetail.title,
      description: examDetail.description,
      level: examDetail.level || 'مبتدی',
      duration: examDetail.duration || '',
    });
    setExamData(nextExamData);
    setReviewFilter(nextSummary.reviewQuestionIds.length > 0 ? 'needs_review' : 'all');
    setOpenQuestionIds(nextSummary.reviewQuestionIds.slice(0, 1));
  }, [examDetail.id, examDetail.updated_at, examDetail.extractionAudit]);

  const visibleQuestions = useMemo(
    () => examData.exam_prep.questions
      .map((question, index) => ({
        question,
        index,
        value: questionValue(question, index),
        review: reviewSummary.questions[index],
        sourceAware: isSourceAwareQuestion(question),
      }))
      .filter((item) => reviewFilter === 'all' || item.review?.needsReview),
    [examData.exam_prep.questions, reviewFilter, reviewSummary.questions],
  );

  const sourceAwareQuestionCount = useMemo(
    () => examData.exam_prep.questions.filter(isSourceAwareQuestion).length,
    [examData.exam_prep.questions],
  );
  const hasSourceAwareProjection = sourceAwareQuestionCount > 0;

  const canAcknowledgeQuestionIssues = (examDetail.extractionVersion ?? 1) <= 1;

  const goToQuestion = (questionId: string) => {
    setOpenQuestionIds((current) => (
      current.includes(questionId) ? current : [...current, questionId]
    ));
    window.setTimeout(() => {
      questionRefs.current[questionId]?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }, 80);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (isUploadingVisual) return;
    await onSave({
      title: formData.title,
      description: formData.description,
      level: formData.level,
      duration: formData.duration,
      // V4 content is owned by the source-aware review flow.  Omitting the
      // legacy payload keeps metadata saves safe and avoids a projection
      // integrity conflict even if a stale client mutates local state.
      ...(hasSourceAwareProjection ? {} : { exam_prep_json: examData }),
    });
  };

  const addQuestion = () => {
    const newQuestion: ExamPrepQuestion = {
      question_id: `q-${Date.now()}`,
      question_text_markdown: '',
      options: [
        { label: '1', text_markdown: '' },
        { label: '2', text_markdown: '' },
        { label: '3', text_markdown: '' },
        { label: '4', text_markdown: '' },
      ],
      correct_option_label: '1',
      correct_option_text_markdown: '',
      teacher_solution_markdown: '',
      final_answer_markdown: '',
      confidence: 1,
      issues: [],
      teacher_reviewed_issue_codes: [],
    };

    setReviewFilter('all');
    setExamData((previous) => ({
      ...previous,
      exam_prep: {
        ...previous.exam_prep,
        questions: [...previous.exam_prep.questions, newQuestion],
      },
    }));
    setOpenQuestionIds((current) => [...current, newQuestion.question_id]);
  };

  const removeQuestion = (index: number) => {
    setExamData((previous) => ({
      ...previous,
      exam_prep: {
        ...previous.exam_prep,
        questions: previous.exam_prep.questions.filter((_, itemIndex) => itemIndex !== index),
      },
    }));
  };

  const attachVisual = (questionId: string, visual: ExamPrepTeacherVisual) => {
    setExamData((previous) => ({
      ...previous,
      exam_prep: {
        ...previous.exam_prep,
        questions: previous.exam_prep.questions.map((question) => (
          question.question_id === questionId
            ? { ...question, visuals: [...(question.visuals ?? []), visual] }
            : question
        )),
      },
    }));
  };

  const removeVisual = (questionId: string, visualId: string | number) => {
    setExamData((previous) => ({
      ...previous,
      exam_prep: {
        ...previous.exam_prep,
        questions: previous.exam_prep.questions.map((question) => (
          question.question_id === questionId
            ? {
                ...question,
                visuals: (question.visuals ?? []).filter(
                  (item) => String(item.id) !== String(visualId),
                ),
              }
            : question
        )),
      },
    }));
  };

  const updateQuestion = (
    index: number,
    updates: Partial<ExamPrepQuestion>,
    options: { preserveReviewDecision?: boolean } = {},
  ) => {
    setExamData((previous) => {
      const questions = [...previous.exam_prep.questions];
      const current = questions[index];
      const next: ExamPrepQuestion = {
        ...current,
        ...updates,
        teacher_reviewed_issue_codes: options.preserveReviewDecision
          ? updates.teacher_reviewed_issue_codes ?? current.teacher_reviewed_issue_codes
          : [],
      };

      if ('correct_option_label' in updates || 'options' in updates) {
        const correctOption = next.options.find(
          (option) => option.label === next.correct_option_label,
        );
        next.correct_option_text_markdown = correctOption?.text_markdown ?? null;
      }
      questions[index] = next;

      return {
        ...previous,
        exam_prep: {
          ...previous.exam_prep,
          questions,
        },
      };
    });
  };

  const upsertOptionText = (questionIndex: number, label: string, text: string) => {
    const question = examData.exam_prep.questions[questionIndex];
    const options = question.options.some((option) => option.label === label)
      ? question.options.map((option) => (
          option.label === label ? { ...option, text_markdown: text } : option
        ))
      : [...question.options, { label, text_markdown: text }];
    updateQuestion(questionIndex, { options });
  };

  const acknowledgeQuestion = (
    questionIndex: number,
    review: ExamQuestionReviewState,
  ) => {
    const question = examData.exam_prep.questions[questionIndex];
    const reviewedCodes = Array.from(new Set([
      ...(question.teacher_reviewed_issue_codes ?? []),
      ...review.issues.map((issue) => issue.code),
    ]));
    const currentPosition = reviewSummary.reviewQuestionIds.indexOf(review.questionId);
    const nextQuestionId = currentPosition >= 0
      ? reviewSummary.reviewQuestionIds[currentPosition + 1]
      : undefined;

    updateQuestion(
      questionIndex,
      { teacher_reviewed_issue_codes: reviewedCodes },
      { preserveReviewDecision: true },
    );
    if (nextQuestionId) {
      window.setTimeout(() => goToQuestion(nextQuestionId), 80);
    }
  };

  const reviewCount = reviewSummary.reviewQuestionIds.length;
  const totalQuestions = examData.exam_prep.questions.length;

  return (
    <form onSubmit={handleSubmit} className="space-y-8 pb-8" dir="rtl">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">اطلاعات کلی</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 md:gap-6">
              <div className="space-y-2">
                <Label htmlFor="title">عنوان آزمون (الزامی)</Label>
                <Input
                  id="title"
                  value={formData.title}
                  maxLength={CLASS_TITLE_MAX_LENGTH}
                  onChange={(event) => setFormData((previous) => ({
                    ...previous,
                    title: event.target.value.slice(0, CLASS_TITLE_MAX_LENGTH),
                  }))}
                  placeholder="عنوان آزمون را وارد کنید"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>حداکثر {CLASS_TITLE_MAX_LENGTH} کاراکتر</span>
                  <span dir="ltr">{formData.title.length}/{CLASS_TITLE_MAX_LENGTH}</span>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="level">سطح (الزامی)</Label>
                <Select
                  value={formData.level}
                  onValueChange={(value: 'مبتدی' | 'متوسط' | 'پیشرفته') =>
                    setFormData((previous) => ({ ...previous, level: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="انتخاب سطح" />
                  </SelectTrigger>
                  <SelectContent>
                    {levelOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="duration">زمان تقریبی</Label>
                <Input
                  id="duration"
                  value={formData.duration}
                  onChange={(event) => setFormData((previous) => ({
                    ...previous,
                    duration: event.target.value,
                  }))}
                  placeholder="مثلاً ۱ ساعت یا ۳۰ دقیقه"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">توضیحات</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(event) => setFormData((previous) => ({
                  ...previous,
                  description: event.target.value,
                }))}
                placeholder="توضیحات آزمون را وارد کنید"
                rows={4}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className={reviewCount > 0 ? 'border-amber-500/50 bg-amber-500/5' : 'border-emerald-500/40 bg-emerald-500/5'}>
        <CardContent className="space-y-4 p-5">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
            <div className="flex items-start gap-3">
              <div className={reviewCount > 0 ? 'rounded-xl bg-amber-500/15 p-2 text-amber-600' : 'rounded-xl bg-emerald-500/15 p-2 text-emerald-600'}>
                {reviewCount > 0 ? <AlertTriangle className="h-5 w-5" /> : <ShieldCheck className="h-5 w-5" />}
              </div>
              <div className="space-y-1">
                <h2 className="font-bold">
                  {reviewCount > 0
                    ? `${reviewCount} سؤال نیازمند بازبینی است`
                    : 'همه سؤال‌ها از کنترل فعلی عبور کرده‌اند'}
                </h2>
                <p className="text-sm leading-6 text-muted-foreground">
                  {reviewCount > 0
                    ? hasSourceAwareProjection
                      ? 'این موارد را در پنل بازبینی منبع‌محور V4 بررسی کنید؛ محتوای سؤال و پاسخ در این فرم قابل ویرایش نیست.'
                      : 'سؤال را باز کنید، دلیل را ببینید، اصلاح لازم را انجام دهید و سپس «تأیید و کنترل مجدد» را بزنید. در پایان همه تغییرات را ذخیره کنید.'
                    : 'در حال حاضر خطای سؤال‌محور حل‌نشده‌ای در audit ذخیره‌شده دیده نمی‌شود.'}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant={reviewFilter === 'needs_review' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setReviewFilter('needs_review')}
                disabled={reviewCount === 0}
              >
                <ListFilter className="h-4 w-4" />
                فقط نیازمند بازبینی ({reviewCount})
              </Button>
              <Button
                type="button"
                variant={reviewFilter === 'all' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setReviewFilter('all')}
              >
                همه سؤال‌ها ({totalQuestions})
              </Button>
              {reviewCount > 0 && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => goToQuestion(reviewSummary.reviewQuestionIds[0])}
                >
                  رفتن به اولین مورد
                  <ChevronLeft className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>

          <div className="flex flex-wrap gap-2 text-xs">
            {reviewSummary.criticalQuestionCount > 0 && (
              <Badge variant="destructive">
                {reviewSummary.criticalQuestionCount} سؤال با خطای بحرانی
              </Badge>
            )}
            {reviewSummary.warningQuestionCount > 0 && (
              <Badge variant="outline" className="border-amber-500/50 text-amber-700 dark:text-amber-300">
                {reviewSummary.warningQuestionCount} سؤال با هشدار
              </Badge>
            )}
          </div>

          {reviewSummary.globalIssues.length > 0 && (
            <div className="rounded-xl border border-destructive/40 bg-destructive/5 p-4">
              <p className="mb-2 text-sm font-bold text-destructive">
                {reviewSummary.globalIssues.length} مشکل کلی به سؤال مشخصی متصل نشده است
              </p>
              <div className="space-y-2">
                {reviewSummary.globalIssues.map((issue, index) => (
                  <div key={`${issue.code}-${index}`} className="text-sm">
                    <span className="font-semibold">{issue.label}</span>
                    <span className="text-muted-foreground"> — {issue.description}</span>
                    {issue.sourcePages.length > 0 && (
                      <span className="mr-2 text-xs text-muted-foreground">
                        صفحه {issue.sourcePages.join('، ')}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <HelpCircle className="h-5 w-5 text-primary" />
            سؤالات و پاسخ‌ها
          </h2>
          <Button
            type="button"
            onClick={addQuestion}
            variant="outline"
            size="sm"
            className="gap-2"
            disabled={hasSourceAwareProjection}
            title={hasSourceAwareProjection ? 'سؤال‌های این آزمون از منبع V4 ساخته شده‌اند و از اینجا قابل تغییر نیستند.' : undefined}
          >
            <Plus className="h-4 w-4" />
            افزودن سؤال جدید
          </Button>
        </div>

        {hasSourceAwareProjection && (
          <div className="rounded-xl border border-blue-500/40 bg-blue-500/5 p-4 text-sm leading-6 text-blue-900 dark:text-blue-100">
            <p className="font-bold">این آزمون از استخراج منبع‌محور V4 ساخته شده است.</p>
            <p>
              متن سؤال، گزینه‌ها و راه‌حل از روی منبع اصلی می‌آیند و در این فرم فقط خواندنی هستند؛
              تصاویر استخراج‌شده همچنان قابل مشاهده‌اند. بازبینی محتوای استخراج‌شده را از پنل V4 انجام دهید؛
              عنوان، توضیحات، سطح و زمان را می‌توانید در همین فرم ویرایش کنید.
            </p>
          </div>
        )}

        {reviewFilter === 'needs_review' && visibleQuestions.length === 0 && totalQuestions > 0 && (
          <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/5 p-6 text-center">
            <CheckCircle2 className="mx-auto mb-2 h-8 w-8 text-emerald-600" />
            <p className="font-semibold">موردی در صف بازبینی باقی نمانده است.</p>
            <p className="mt-1 text-sm text-muted-foreground">
              اکنون «ذخیره تمام تغییرات آزمون» را بزنید تا سرور دوباره کنترل کند.
            </p>
          </div>
        )}

        <Accordion
          type="multiple"
          value={openQuestionIds}
          onValueChange={setOpenQuestionIds}
          className="space-y-4"
        >
          {visibleQuestions.map(({ question, index: questionIndex, value, review, sourceAware }) => (
            <div
              key={value}
              ref={(element) => { questionRefs.current[value] = element; }}
              className="scroll-mt-28"
            >
              <AccordionItem
                value={value}
                className={review?.needsReview
                  ? 'overflow-hidden rounded-xl border border-amber-500/50 bg-card'
                  : 'overflow-hidden rounded-xl border border-border/60 bg-card'}
              >
                <div className="group/title relative">
                  <AccordionTrigger className="px-4 py-4 transition-colors hover:bg-muted/30 hover:no-underline">
                    <div className="flex min-w-0 flex-1 items-center gap-3 text-right">
                      <span className={review?.criticalCount
                        ? 'flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-destructive/15 text-xs font-bold text-destructive'
                        : review?.needsReview
                          ? 'flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-500/15 text-xs font-bold text-amber-700 dark:text-amber-300'
                          : 'flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs text-primary'}
                      >
                        {review?.questionNumber || questionIndex + 1}
                      </span>
                      <span className="min-w-0 flex-1 truncate text-sm font-bold">
                        {question.question_text_markdown
                          ? question.question_text_markdown.split('\n')[0]
                          : 'سؤال جدید'}
                      </span>
                      {review?.needsReview && (
                        <Badge
                          variant={review.criticalCount > 0 ? 'destructive' : 'outline'}
                          className={review.criticalCount > 0 ? '' : 'border-amber-500/50 text-amber-700 dark:text-amber-300'}
                        >
                          نیازمند بازبینی · {review.issues.length}
                        </Badge>
                      )}
                    </div>
                  </AccordionTrigger>

                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="absolute left-12 top-1/2 z-10 -translate-y-1/2 text-destructive opacity-0 transition-opacity group-hover/title:opacity-100"
                    onClick={(event) => {
                      event.stopPropagation();
                      removeQuestion(questionIndex);
                    }}
                    disabled={sourceAware}
                    aria-label={`حذف سؤال ${questionIndex + 1}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>

                <AccordionContent className="space-y-6 px-4 pb-6 pt-4">
                  {review?.needsReview && (
                    <div className="space-y-4 rounded-xl border border-amber-500/50 bg-amber-500/5 p-4">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="h-5 w-5 text-amber-600" />
                        <p className="font-bold">چرا این سؤال نیازمند بازبینی است؟</p>
                      </div>
                      <div className="space-y-3">
                        {review.issues.map((issue) => (
                          <div key={issue.code} className="rounded-lg border border-border/60 bg-background/70 p-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant={issue.severity === 'critical' ? 'destructive' : 'outline'}>
                                {issue.severity === 'critical' ? 'بحرانی' : 'هشدار'}
                              </Badge>
                              <span className="text-sm font-semibold">{issue.label}</span>
                              {issue.sourcePages.length > 0 && (
                                <span className="text-xs text-muted-foreground">
                                  صفحه منبع: {issue.sourcePages.join('، ')}
                                </span>
                              )}
                            </div>
                            <p className="mt-2 text-sm leading-6 text-muted-foreground">
                              {issue.description}
                            </p>
                          </div>
                        ))}
                      </div>
                      <div className="flex flex-col justify-between gap-3 border-t border-amber-500/20 pt-3 sm:flex-row sm:items-center">
                        <p className="text-xs leading-5 text-muted-foreground">
                          تأیید معلم فقط خطاهای قضاوتی را رفع می‌کند؛ گزینه خالی، نبود پاسخ و سایر خطاهای قطعی پس از ذخیره دوباره برمی‌گردند.
                        </p>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => acknowledgeQuestion(questionIndex, review)}
                          disabled={!canAcknowledgeQuestionIssues || sourceAware}
                          title={sourceAware ? 'بازبینی سؤال‌های V4 از پنل منبع‌محور انجام می‌شود.' : undefined}
                        >
                          <ShieldCheck className="h-4 w-4" />
                          تأیید و کنترل مجدد
                        </Button>
                      </div>
                    </div>
                  )}

                  {!sourceAware && (
                    <QuestionVisualUploader
                      sessionId={examDetail.id}
                      questionId={value}
                      optionLabels={question.options.map((option) => option.label)}
                      disabled={isSaving || isUploadingVisual}
                      onUploadStateChange={setIsUploadingVisual}
                      onVisualUploaded={(visual) => attachVisual(value, visual)}
                    />
                  )}

                  {visualsForRole(question.visuals, 'question').length > 0 && (
                    <div className="grid gap-3 sm:grid-cols-2">
                      {visualsForRole(question.visuals, 'question').map((visual) => (
                        <TeacherVisualCard
                          key={String(visual.id)}
                          visual={visual}
                          sessionId={examDetail.id}
                          alt={visual.altText || 'تصویر مرتبط با صورت سؤال'}
                          className="h-auto max-h-[60vh] min-h-32 w-full rounded-md border object-contain"
                          removable={!sourceAware}
                          disabled={isSaving || isUploadingVisual}
                          onRemove={(visualId) => removeVisual(value, visualId)}
                        />
                      ))}
                    </div>
                  )}

                  <div className="space-y-2">
                    <Label>متن اصلی سؤال (صورت سؤال)</Label>
                    <Textarea
                      value={question.question_text_markdown || ''}
                      onChange={(event) => updateQuestion(questionIndex, {
                        question_text_markdown: event.target.value,
                      })}
                      placeholder="صورت سؤال را به همراه فرمول‌های LaTeX وارد کنید"
                      rows={3}
                      className="font-mono text-sm"
                      disabled={sourceAware}
                    />
                  </div>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    {editableOptionLabels(question.options).map((label, optionIndex) => {
                      const option = question.options.find((item) => item.label === label);
                      return (
                        <div key={`${label}-${optionIndex}`} className="space-y-1">
                          <div className="flex items-center justify-between">
                            <Label className="text-xs text-muted-foreground">
                              گزینه {label}
                            </Label>
                            {question.correct_option_label === label && (
                              <span className="flex items-center gap-1 rounded-full bg-green-100 px-1.5 text-[10px] text-green-700">
                                <CheckCircle2 className="h-2 w-2" />
                                پاسخ صحیح
                              </span>
                            )}
                          </div>
                          <Input
                            value={option?.text_markdown || ''}
                            onChange={(event) => upsertOptionText(
                              questionIndex,
                              label,
                              event.target.value,
                            )}
                            placeholder={`متن گزینه ${label}`}
                            disabled={sourceAware}
                          />
                          {question.visuals
                            ?.filter(
                              (visual) =>
                                visual.role === 'option' && visualMatchesOption(visual, label),
                            )
                            .map((visual) => (
                              <TeacherVisualCard
                                key={String(visual.id)}
                                visual={visual}
                                sessionId={examDetail.id}
                                alt={visual.altText || `تصویر گزینه ${label}`}
                                className="mt-2 h-auto max-h-64 min-h-24 w-full rounded-md border object-contain"
                                removable={!sourceAware}
                                disabled={isSaving || isUploadingVisual}
                                onRemove={(visualId) => removeVisual(value, visualId)}
                              />
                            ))}
                        </div>
                      );
                    })}
                  </div>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2 md:gap-6">
                    <div className="space-y-2">
                      <Label>انتخاب گزینه صحیح</Label>
                      <Select
                        value={question.correct_option_label || ''}
                        disabled={sourceAware}
                        onValueChange={(value) => updateQuestion(questionIndex, {
                          correct_option_label: value,
                        })}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="پاسخ صحیح را انتخاب کنید" />
                        </SelectTrigger>
                        <SelectContent>
                          {editableOptionLabels(question.options).map((label) => (
                            <SelectItem key={label} value={label}>
                              گزینه {label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2">
                      <Label>خروجی نهایی (نتیجه)</Label>
                      <Input
                        value={question.final_answer_markdown || ''}
                        onChange={(event) => updateQuestion(questionIndex, {
                          final_answer_markdown: event.target.value,
                        })}
                        placeholder="مثلاً: گزینه ب یا x=5"
                        disabled={sourceAware}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>تحلیل و راه‌حل مدرس</Label>
                    <Textarea
                      value={question.teacher_solution_markdown || ''}
                      onChange={(event) => updateQuestion(questionIndex, {
                        teacher_solution_markdown: event.target.value,
                      })}
                      placeholder="توضیحات و راه‌حل تشریحی مدرس را اینجا وارد کنید"
                      rows={6}
                      className="min-h-[150px] resize-none bg-muted/30 md:resize-y"
                      disabled={sourceAware}
                    />
                    {visualsForRole(question.visuals, 'solution').length > 0 && (
                      <div className="grid gap-3 sm:grid-cols-2">
                        {visualsForRole(question.visuals, 'solution').map((visual) => (
                          <TeacherVisualCard
                            key={String(visual.id)}
                            visual={visual}
                            sessionId={examDetail.id}
                            alt={visual.altText || 'تصویر راه‌حل سؤال'}
                            className="h-auto max-h-[60vh] min-h-32 w-full rounded-md border object-contain"
                            removable={!sourceAware}
                            disabled={isSaving || isUploadingVisual}
                            onRemove={(visualId) => removeVisual(value, visualId)}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </AccordionContent>
              </AccordionItem>
            </div>
          ))}
        </Accordion>

        {totalQuestions === 0 && (
          <div className="rounded-lg border-2 border-dashed border-muted bg-muted/20 py-10 text-center">
            <HelpCircle className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
            <p className="text-muted-foreground">هنوز هیچ سؤالی برای این آزمون ثبت نشده است.</p>
            <Button
              type="button"
              onClick={addQuestion}
              variant="link"
              className="mt-2"
              disabled={hasSourceAwareProjection}
            >
              ایجاد اولین سؤال
            </Button>
          </div>
        )}
      </div>

      <div className="sticky bottom-0 left-0 right-0 z-40 flex flex-col items-stretch justify-between gap-3 border-t bg-background/95 p-4 backdrop-blur sm:flex-row sm:items-center">
        <p className="text-xs text-muted-foreground">
          {reviewCount > 0
            ? `${reviewCount} سؤال هنوز در صف بازبینی است.`
            : 'پس از ذخیره، وضعیت انتشار و audit دوباره محاسبه می‌شود.'}
        </p>
        <Button type="submit" disabled={isSaving || isUploadingVisual} size="lg" className="px-8 shadow-lg">
          {isSaving ? (
            <Loader2 className="ml-2 h-5 w-5 animate-spin" />
          ) : (
            <Save className="ml-2 h-5 w-5" />
          )}
          ذخیره تمام تغییرات آزمون
        </Button>
      </div>
    </form>
  );
}
