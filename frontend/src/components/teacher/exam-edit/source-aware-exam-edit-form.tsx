'use client';

import { useEffect, useState } from 'react';
import { CheckCircle2, ImageIcon, Loader2, Save, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { ProtectedExamVisual } from '@/components/exam-prep/protected-exam-visual';
import {
  resolveExamVisualUrl,
  visualMatchesOption,
  visualsForRole,
} from '@/lib/exam-visuals';
import type {
  ExamPrepData,
  ExamPrepQuestion,
  ExamPrepSessionDetail,
  ExamPrepSessionUpdatePayload,
} from '@/services/classes-service';

interface SourceAwareExamEditFormProps {
  examDetail: ExamPrepSessionDetail;
  onSave: (data: ExamPrepSessionUpdatePayload) => Promise<void>;
  isSaving?: boolean;
}

function initialData(detail: ExamPrepSessionDetail): ExamPrepData {
  return detail.exam_prep_data || {
    exam_prep: { title: detail.title, questions: [] },
  };
}

export function SourceAwareExamEditForm({
  examDetail,
  onSave,
  isSaving,
}: SourceAwareExamEditFormProps) {
  const [metadata, setMetadata] = useState({
    title: examDetail.title,
    description: examDetail.description,
    level: examDetail.level || 'مبتدی',
    duration: examDetail.duration || '',
  });
  const [examData, setExamData] = useState<ExamPrepData>(() => initialData(examDetail));

  useEffect(() => {
    setMetadata({
      title: examDetail.title,
      description: examDetail.description,
      level: examDetail.level || 'مبتدی',
      duration: examDetail.duration || '',
    });
    setExamData(initialData(examDetail));
  }, [examDetail.id, examDetail.updated_at]);

  const updateQuestion = (index: number, patch: Partial<ExamPrepQuestion>) => {
    setExamData((previous) => {
      const questions = [...previous.exam_prep.questions];
      const next = { ...questions[index], ...patch };
      if ('correct_option_label' in patch || 'options' in patch) {
        const selected = next.options.find(
          (option) => option.label === next.correct_option_label,
        );
        next.correct_option_text_markdown = selected?.text_markdown ?? null;
      }
      questions[index] = next;
      return {
        ...previous,
        exam_prep: { ...previous.exam_prep, questions },
      };
    });
  };

  const updateOption = (questionIndex: number, optionIndex: number, text: string) => {
    const question = examData.exam_prep.questions[questionIndex];
    const options = question.options.map((option, index) => (
      index === optionIndex ? { ...option, text_markdown: text } : option
    ));
    updateQuestion(questionIndex, { options });
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    await onSave({
      title: metadata.title,
      description: metadata.description,
      level: metadata.level,
      duration: metadata.duration,
      exam_prep_json: examData,
    });
  };

  return (
    <form onSubmit={submit} className="space-y-6 pb-10" dir="rtl">
      <div className="rounded-2xl border border-blue-500/40 bg-blue-500/5 p-4 text-sm leading-7">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-1 h-5 w-5 shrink-0 text-blue-600" />
          <div>
            <p className="font-black">بازبینی منبع‌محور</p>
            <p className="text-muted-foreground">
              تصویر PDF مرجع نهایی است. متن سؤال، گزینه‌ها، پاسخ صحیح و راه‌حل را با تصویر اصلی
              مقایسه و در صورت نیاز اصلاح کنید. برای حفظ اتصال به PDF، افزودن/حذف سؤال و تغییر
              شناسه‌ها یا برچسب گزینه‌ها قفل است.
            </p>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">اطلاعات آزمون</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>عنوان</Label>
            <Input
              value={metadata.title}
              onChange={(event) => setMetadata((value) => ({ ...value, title: event.target.value }))}
            />
          </div>
          <div className="space-y-2">
            <Label>سطح</Label>
            <select
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={metadata.level}
              onChange={(event) => setMetadata((value) => ({ ...value, level: event.target.value }))}
            >
              <option value="مبتدی">مبتدی</option>
              <option value="متوسط">متوسط</option>
              <option value="پیشرفته">پیشرفته</option>
            </select>
          </div>
          <div className="space-y-2">
            <Label>زمان</Label>
            <Input
              value={metadata.duration}
              onChange={(event) => setMetadata((value) => ({ ...value, duration: event.target.value }))}
            />
          </div>
          <div className="space-y-2 md:col-span-2">
            <Label>توضیحات</Label>
            <Textarea
              value={metadata.description}
              onChange={(event) => setMetadata((value) => ({ ...value, description: event.target.value }))}
              rows={3}
            />
          </div>
        </CardContent>
      </Card>

      <div className="space-y-5">
        {examData.exam_prep.questions.map((question, questionIndex) => {
          const questionVisuals = visualsForRole(question.visuals, 'question');
          const solutionVisuals = visualsForRole(question.visuals, 'solution');
          return (
            <Card key={question.question_id} className="overflow-hidden">
              <CardHeader className="border-b bg-muted/20">
                <div className="flex items-center justify-between gap-3">
                  <CardTitle className="text-base">سؤال {questionIndex + 1}</CardTitle>
                  <span className="flex items-center gap-1 text-xs text-emerald-700 dark:text-emerald-300">
                    <CheckCircle2 className="h-4 w-4" />
                    اتصال منبع قفل است
                  </span>
                </div>
              </CardHeader>
              <CardContent className="space-y-6 p-4 sm:p-6">
                {questionVisuals.length > 0 && (
                  <div className="space-y-2 rounded-xl border border-primary/20 bg-primary/5 p-3">
                    <p className="flex items-center gap-2 text-sm font-bold">
                      <ImageIcon className="h-4 w-4" />
                      مرجع اصلی صورت سؤال
                    </p>
                    <div className="grid gap-3 lg:grid-cols-2">
                      {questionVisuals.map((visual) => {
                        const url = resolveExamVisualUrl(visual, examDetail.id);
                        return url ? (
                          <ProtectedExamVisual
                            key={String(visual.id)}
                            url={url}
                            alt={visual.altText || 'تصویر اصلی سؤال'}
                            className="max-h-[70vh] w-full rounded-lg border bg-white object-contain"
                          />
                        ) : null;
                      })}
                    </div>
                  </div>
                )}

                <div className="space-y-2">
                  <Label>متن سؤال</Label>
                  <Textarea
                    value={question.question_text_markdown || ''}
                    rows={4}
                    className="font-mono text-sm"
                    onChange={(event) => updateQuestion(questionIndex, {
                      question_text_markdown: event.target.value,
                    })}
                  />
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  {question.options.map((option, optionIndex) => (
                    <div key={`${question.question_id}-${option.label}`} className="space-y-2 rounded-xl border p-3">
                      <div className="flex items-center justify-between">
                        <Label>گزینه {option.label}</Label>
                        {question.correct_option_label === option.label && (
                          <span className="text-xs font-bold text-emerald-600">پاسخ صحیح</span>
                        )}
                      </div>
                      <Textarea
                        value={option.text_markdown || ''}
                        rows={2}
                        onChange={(event) => updateOption(
                          questionIndex,
                          optionIndex,
                          event.target.value,
                        )}
                      />
                      {question.visuals
                        ?.filter((visual) => visual.role === 'option' && visualMatchesOption(visual, option.label))
                        .map((visual) => {
                          const url = resolveExamVisualUrl(visual, examDetail.id);
                          return url ? (
                            <ProtectedExamVisual
                              key={String(visual.id)}
                              url={url}
                              alt={visual.altText || `تصویر گزینه ${option.label}`}
                              className="max-h-56 w-full rounded-lg border object-contain"
                            />
                          ) : null;
                        })}
                    </div>
                  ))}
                </div>

                {question.options.length > 0 && (
                  <div className="space-y-2">
                    <Label>پاسخ صحیح — حتماً با منبع کنترل شود</Label>
                    <select
                      className="h-11 w-full rounded-md border border-input bg-background px-3 font-bold"
                      value={question.correct_option_label || ''}
                      onChange={(event) => updateQuestion(questionIndex, {
                        correct_option_label: event.target.value,
                      })}
                    >
                      <option value="">انتخاب پاسخ صحیح</option>
                      {question.options.map((option) => (
                        <option key={option.label} value={option.label}>
                          گزینه {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="space-y-2">
                  <Label>نتیجه / پاسخ نهایی</Label>
                  <Input
                    value={question.final_answer_markdown || ''}
                    onChange={(event) => updateQuestion(questionIndex, {
                      final_answer_markdown: event.target.value,
                    })}
                  />
                </div>

                {solutionVisuals.length > 0 && (
                  <div className="space-y-2 rounded-xl border border-amber-500/25 bg-amber-500/5 p-3">
                    <p className="flex items-center gap-2 text-sm font-bold">
                      <ImageIcon className="h-4 w-4" />
                      مرجع اصلی پاسخ تشریحی
                    </p>
                    <div className="grid gap-3 lg:grid-cols-2">
                      {solutionVisuals.map((visual) => {
                        const url = resolveExamVisualUrl(visual, examDetail.id);
                        return url ? (
                          <ProtectedExamVisual
                            key={String(visual.id)}
                            url={url}
                            alt={visual.altText || 'تصویر اصلی پاسخ تشریحی'}
                            className="max-h-[75vh] w-full rounded-lg border bg-white object-contain"
                          />
                        ) : null;
                      })}
                    </div>
                  </div>
                )}

                <div className="space-y-2">
                  <Label>راه‌حل تشریحی</Label>
                  <Textarea
                    value={question.teacher_solution_markdown || ''}
                    rows={8}
                    className="font-mono text-sm"
                    onChange={(event) => updateQuestion(questionIndex, {
                      teacher_solution_markdown: event.target.value,
                    })}
                  />
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="sticky bottom-0 z-40 flex items-center justify-between gap-3 rounded-xl border bg-background/95 p-4 shadow-lg backdrop-blur">
        <p className="hidden text-xs text-muted-foreground sm:block">
          ذخیره فقط متن‌های قابل ویرایش را تغییر می‌دهد؛ اتصال PDF و تصاویر اصلی ثابت می‌ماند.
        </p>
        <Button type="submit" size="lg" disabled={isSaving} className="mr-auto min-w-48">
          {isSaving ? <Loader2 className="h-5 w-5 animate-spin" /> : <Save className="h-5 w-5" />}
          ذخیره اصلاحات
        </Button>
      </div>
    </form>
  );
}
