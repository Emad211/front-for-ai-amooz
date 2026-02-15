'use client';

import { Button } from '@/components/ui/button';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { ChevronLeft, ChevronRight, CheckCircle2, XCircle, Loader2, Lightbulb, MessageCircle } from 'lucide-react';
import { Question } from '@/types';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { toPersianOptionLabel } from '@/lib/persian-option-label';
import type { QuestionFeedback } from '@/hooks/use-exam';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';

interface QuestionContentProps {
  question: Question | null;
  totalQuestions: number;
  onNext: () => void;
  onPrev: () => void;
  onSubmit: (questionId: string, answerId: string) => void;
  onCheckAnswer: (questionId: string) => Promise<QuestionFeedback | null>;
  onFinalize: () => void | Promise<void>;
  isSubmitting?: boolean;
  isFinalized?: boolean;
  isCheckingAnswer?: boolean;
  selectedOptionId?: string;
  unansweredCount?: number;
  feedback?: QuestionFeedback | null;
}

/** Map question type to a Persian badge label. */
function questionTypeBadge(type?: string): { label: string; color: string } | null {
  switch (type) {
    case 'true_false':
      return { label: 'صحیح / غلط', color: 'bg-blue-500/15 text-blue-400' };
    case 'fill_blank':
      return { label: 'جای خالی', color: 'bg-amber-500/15 text-amber-400' };
    case 'short_answer':
      return { label: 'تشریحی', color: 'bg-purple-500/15 text-purple-400' };
    case 'multiple_choice':
      return { label: 'چندگزینه‌ای', color: 'bg-green-500/15 text-green-400' };
    default:
      return null;
  }
}

/**
 * Replace blank placeholders in question text with a visible underline.
 */
function renderBlankPlaceholders(text: string): string {
  return text
    .replace(/\\\{blank\\\}/gi, ' ________ ')
    .replace(/\{\{blank\}\}/gi, ' ________ ')
    .replace(/\{blank\}/gi, ' ________ ');
}

export const QuestionContent = ({
  question,
  totalQuestions,
  onNext,
  onPrev,
  onSubmit,
  onCheckAnswer,
  onFinalize,
  isSubmitting,
  isFinalized,
  isCheckingAnswer,
  selectedOptionId,
  unansweredCount,
  feedback,
}: QuestionContentProps) => {
  if (!question) return null;

  const badge = questionTypeBadge(question.type);
  const qType = question.type || 'multiple_choice';
  const displayText =
    qType === 'fill_blank' ? renderBlankPlaceholders(question.text) : question.text;

  const hasAnswer = Boolean(selectedOptionId?.trim());
  const alreadyCorrect = feedback?.isCorrect === true;
  const canCheck = hasAnswer && !alreadyCorrect && !isFinalized && !isCheckingAnswer;

  return (
    <section className="flex-1 flex flex-col justify-center items-center gap-8 p-4 sm:p-6 md:p-8 w-full min-h-full">
      <div className="bg-card border border-border rounded-2xl p-4 sm:p-6 shadow-lg flex flex-col w-full max-w-4xl my-auto">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold text-primary">سوال {question.number}</h2>
            <span className="text-xs font-semibold text-muted-foreground bg-secondary px-2 py-1 rounded-md">
              {question.number} / {totalQuestions}
            </span>
            {badge && (
              <span className={`text-xs font-semibold px-2 py-1 rounded-md ${badge.color}`}>
                {badge.label}
              </span>
            )}
            {feedback && feedback.attempts > 0 && (
              <span className="text-xs font-semibold px-2 py-1 rounded-md bg-secondary text-muted-foreground">
                {feedback.attempts} تلاش
              </span>
            )}
          </div>
        </div>
        <div className="space-y-6 flex-grow">
          <MarkdownWithMath
            markdown={displayText}
            renderKey={question.id}
            className="text-foreground leading-8 text-base sm:text-lg"
          />

          {/* ===== TRUE / FALSE ===== */}
          {qType === 'true_false' && (
            <RadioGroup
              key={question.id}
              value={selectedOptionId || ''}
              onValueChange={(value) => onSubmit(question.id, value)}
              dir="rtl"
              className="grid grid-cols-2 gap-3 sm:gap-4"
              disabled={Boolean(isSubmitting) || Boolean(isFinalized) || alreadyCorrect}
            >
              {[
                { value: 'صحیح', label: 'صحیح ✓' },
                { value: 'غلط', label: 'غلط ✗' },
              ].map((opt) => (
                <Label
                  key={opt.value}
                  htmlFor={`tf-${question.id}-${opt.value}`}
                  className="flex items-center justify-center gap-3 p-4 bg-background border border-border rounded-lg cursor-pointer hover:bg-secondary/50 has-[:checked]:bg-primary/10 has-[:checked]:border-primary text-center"
                >
                  <RadioGroupItem value={opt.value} id={`tf-${question.id}-${opt.value}`} />
                  <span className="text-sm sm:text-base font-semibold">{opt.label}</span>
                </Label>
              ))}
            </RadioGroup>
          )}

          {/* ===== FILL IN THE BLANK ===== */}
          {qType === 'fill_blank' && (
            <div className="mt-3">
              <textarea
                value={selectedOptionId || ''}
                onChange={(e) => onSubmit(question.id, e.target.value)}
                disabled={Boolean(isSubmitting) || Boolean(isFinalized) || alreadyCorrect}
                className="w-full min-h-20 rounded-lg border border-border bg-background p-3 text-sm text-foreground resize-y"
                placeholder="پاسخ خود را برای جای خالی بنویسید..."
                dir="rtl"
              />
            </div>
          )}

          {/* ===== SHORT ANSWER ===== */}
          {qType === 'short_answer' && (
            <div className="mt-3">
              <textarea
                value={selectedOptionId || ''}
                onChange={(e) => onSubmit(question.id, e.target.value)}
                disabled={Boolean(isSubmitting) || Boolean(isFinalized) || alreadyCorrect}
                className="w-full min-h-28 rounded-lg border border-border bg-background p-3 text-sm text-foreground resize-y"
                placeholder="پاسخ تشریحی خود را بنویسید..."
                dir="rtl"
              />
            </div>
          )}

          {/* ===== MULTIPLE CHOICE ===== */}
          {qType === 'multiple_choice' && question.options.length > 0 && (
            <RadioGroup
              key={question.id}
              value={selectedOptionId || ''}
              onValueChange={(value) => onSubmit(question.id, value)}
              dir="rtl"
              className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4"
              disabled={Boolean(isSubmitting) || Boolean(isFinalized) || alreadyCorrect}
            >
              {question.options.map((option, optionIndex) => {
                const displayLabel = toPersianOptionLabel(option.label, optionIndex);
                return (
                  <Label
                    key={option.id}
                    htmlFor={`option-${question.id}-${option.id}`}
                    className="flex items-center justify-between p-3 sm:p-4 bg-background border border-border rounded-lg cursor-pointer hover:bg-secondary/50 has-[:checked]:bg-primary/10 has-[:checked]:border-primary"
                  >
                    <div className="flex items-center gap-3">
                      <RadioGroupItem value={option.label} id={`option-${question.id}-${option.id}`} />
                      <span className="text-sm sm:text-base">{displayLabel})</span>
                      <div className="text-sm sm:text-base">
                        <MarkdownWithMath
                          markdown={option.text}
                          renderKey={`${question.id}-${option.id}`}
                          className="leading-7"
                        />
                      </div>
                    </div>
                  </Label>
                );
              })}
            </RadioGroup>
          )}

          {/* ===== PER-QUESTION CHECK BUTTON ===== */}
          {!isFinalized && (
            <div className="flex justify-center mt-2">
              <Button
                onClick={() => void onCheckAnswer(question.id)}
                disabled={!canCheck}
                className="px-6"
                variant={alreadyCorrect ? 'outline' : 'default'}
              >
                {isCheckingAnswer ? (
                  <>
                    <Loader2 className="ml-2 h-4 w-4 animate-spin" />
                    در حال بررسی...
                  </>
                ) : alreadyCorrect ? (
                  <>
                    <CheckCircle2 className="ml-2 h-4 w-4 text-green-500" />
                    پاسخ صحیح
                  </>
                ) : (
                  'ثبت و بررسی پاسخ'
                )}
              </Button>
            </div>
          )}

          {/* ===== FEEDBACK AREA ===== */}
          {feedback && !isFinalized && (
            <div className={`rounded-xl border p-4 mt-2 ${
              feedback.isCorrect
                ? 'bg-green-500/10 border-green-500/30'
                : 'bg-amber-500/10 border-amber-500/30'
            }`} dir="rtl">
              {feedback.isCorrect ? (
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-green-600">آفرین! پاسخ شما صحیح است.</p>
                    <p className="text-xs text-muted-foreground">
                      تعداد تلاش: {feedback.attempts} — امتیاز: {feedback.scoreForQuestion}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-start gap-3">
                    <XCircle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
                    <div className="space-y-1">
                      <p className="text-sm font-semibold text-amber-600">پاسخ شما صحیح نیست. دوباره تلاش کنید!</p>
                      <p className="text-xs text-muted-foreground">تلاش شماره {feedback.attempts}</p>
                    </div>
                  </div>
                  {feedback.hint && (
                    <div className="flex items-start gap-2 bg-background/50 rounded-lg p-3">
                      <Lightbulb className="h-4 w-4 text-amber-400 flex-shrink-0 mt-0.5" />
                      <p className="text-sm leading-6">{feedback.hint}</p>
                    </div>
                  )}
                  {feedback.encouragement && (
                    <div className="flex items-start gap-2 bg-background/50 rounded-lg p-3">
                      <MessageCircle className="h-4 w-4 text-blue-400 flex-shrink-0 mt-0.5" />
                      <p className="text-sm leading-6 text-muted-foreground">{feedback.encouragement}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="mt-6 flex flex-col sm:flex-row gap-4 justify-between items-center border-t border-border pt-4">
          <div className="flex gap-2 w-full sm:w-auto">
            <Button variant="outline" className="flex-1 sm:flex-none" onClick={onPrev}>
              <ChevronRight className="ml-2 h-4 w-4" />
              قبلی
            </Button>
            <Button variant="outline" className="flex-1 sm:flex-none" onClick={onNext}>
              بعدی
              <ChevronLeft className="mr-2 h-4 w-4" />
            </Button>
          </div>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                size="lg"
                className="w-full sm:w-auto bg-primary text-primary-foreground hover:bg-primary/90"
                disabled={Boolean(isSubmitting) || Boolean(isFinalized)}
              >
                {isFinalized ? 'آزمون ثبت نهایی شد' : isSubmitting ? 'در حال ثبت...' : 'پایان آزمون'}
                <ChevronLeft className="mr-2 h-4 w-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent dir="rtl" className="text-right">
              <AlertDialogHeader>
                <AlertDialogTitle className="text-right">آیا از ثبت نهایی آزمون مطمئن هستید؟</AlertDialogTitle>
                <AlertDialogDescription className="text-right">
                  با تایید این مرحله، آزمون نهایی می‌شود و دیگر امکان تغییر پاسخ‌ها وجود ندارد.
                  {typeof unansweredCount === 'number' && unansweredCount > 0 ? ` (تعداد سوالات بدون پاسخ: ${unansweredCount})` : ''}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter className="gap-2">
                <AlertDialogCancel disabled={Boolean(isSubmitting)}>انصراف</AlertDialogCancel>
                <AlertDialogAction
                  disabled={Boolean(isSubmitting) || Boolean(isFinalized)}
                  onClick={() => {
                    void onFinalize();
                  }}
                >
                  تایید و ثبت نهایی
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>
    </section>
  );
};
