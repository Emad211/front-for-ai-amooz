'use client';

import React, { useState, useCallback } from 'react';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight, RotateCcw, Check, X } from 'lucide-react';

interface QuizQuestion {
  question: string;
  options?: string[];
  correct_answer?: string;
  answer?: string; // Fallback for practice_test format
}

interface InteractiveQuizProps {
  questions: QuizQuestion[];
}

export function InteractiveQuiz({ questions }: InteractiveQuizProps) {
  const qs = Array.isArray(questions) ? questions : [];
  const total = qs.length;

  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, { selected: number | null; correct: boolean }>>({});
  const [showResult, setShowResult] = useState(false);

  const current = qs[currentIndex] ?? { question: '', options: [], correct_answer: '', answer: '' };
  const currentAnswer = answers[currentIndex];

  const selectOption = useCallback(
    (optIndex: number) => {
      if (currentAnswer) return; // Already answered
      const selectedText = String(current.options?.[optIndex] ?? '').trim();
      const correctText = String(current.correct_answer || current.answer || '').trim();
      const isCorrect =
        selectedText === correctText ||
        selectedText.includes(correctText) ||
        (correctText && selectedText.toLowerCase() === correctText.toLowerCase());
      setAnswers((prev) => ({ ...prev, [currentIndex]: { selected: optIndex, correct: isCorrect } }));
    },
    [current, currentAnswer, currentIndex]
  );

  const next = useCallback(() => {
    if (currentIndex < total - 1) {
      setCurrentIndex((i) => i + 1);
    } else {
      setShowResult(true);
    }
  }, [currentIndex, total]);

  const prev = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex((i) => i - 1);
    }
  }, [currentIndex]);

  const reset = useCallback(() => {
    setCurrentIndex(0);
    setAnswers({});
    setShowResult(false);
  }, []);

  if (total === 0) {
    return <div className="text-sm text-muted-foreground p-4 text-center">سوالی موجود نیست.</div>;
  }

  // Calculate score
  const correctCount = Object.values(answers).filter((a) => a.correct).length;

  if (showResult) {
    return (
      <div className="w-full py-4 text-center">
        <div className="text-lg font-bold mb-2">نتیجه آزمون</div>
        <div className="text-2xl font-bold text-primary mb-4">
          {correctCount} / {total}
        </div>
        <p className="text-sm text-muted-foreground mb-4">
          {correctCount === total ? 'عالی! همه پاسخ‌ها درست بود 🎉' : correctCount >= total / 2 ? 'خوب بود! 👍' : 'بیشتر تمرین کن 💪'}
        </p>
        <Button variant="outline" size="sm" onClick={reset}>
          <RotateCcw className="h-4 w-4 ml-1" />
          شروع مجدد
        </Button>
      </div>
    );
  }

  return (
    <div className="w-full py-2">
      {/* Header */}
      <div className="flex items-center justify-between mb-3 px-1">
        <span className="text-xs font-medium text-muted-foreground">❓ کوئیز</span>
        <span className="text-xs text-muted-foreground">
          {currentIndex + 1} / {total}
        </span>
      </div>

      {/* Question */}
      <div className="mb-3 p-3 rounded-xl border border-border bg-card">
        <MarkdownWithMath markdown={String(current.question ?? '')} className="text-sm font-medium" renderKey={`q-${currentIndex}`} />
      </div>

      {/* Options */}
      {Array.isArray(current.options) && current.options.length > 0 ? (
        <div className="space-y-2 mb-4">
          {current.options.map((opt, i) => {
            const isSelected = currentAnswer?.selected === i;
            const isCorrectOption =
              String(opt).trim() === String(current.correct_answer ?? '').trim() ||
              String(opt).includes(String(current.correct_answer ?? ''));
            const showCorrect = currentAnswer && isCorrectOption;
            const showWrong = currentAnswer && isSelected && !currentAnswer.correct;

            return (
              <div
                key={i}
                onClick={() => selectOption(i)}
                className={cn(
                  'rounded-lg border p-2.5 cursor-pointer transition-all flex items-start gap-2',
                  !currentAnswer && 'border-border bg-card hover:border-primary/40',
                  showCorrect && 'border-green-500/50 bg-green-500/10',
                  showWrong && 'border-destructive/50 bg-destructive/10',
                  currentAnswer && !showCorrect && !showWrong && 'opacity-50 cursor-default'
                )}
              >
                <span className="flex-shrink-0 w-5 h-5 rounded-full border border-border flex items-center justify-center text-[10px] font-bold">
                  {showCorrect ? <Check className="h-3 w-3 text-green-600" /> : showWrong ? <X className="h-3 w-3 text-destructive" /> : String.fromCharCode(65 + i)}
                </span>
                <MarkdownWithMath markdown={String(opt)} className="text-xs flex-1" renderKey={`opt-${currentIndex}-${i}-${currentAnswer ? 'a' : 'u'}`} />
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-xs text-muted-foreground text-center mb-4">گزینه‌ای موجود نیست</div>
      )}

      {/* Feedback */}
      {currentAnswer && (
        <div
          className={cn(
            'mb-3 text-center text-xs py-2 px-3 rounded-lg border',
            currentAnswer.correct ? 'border-green-500/30 bg-green-500/10 text-green-600' : 'border-destructive/30 bg-destructive/10 text-destructive'
          )}
        >
          {currentAnswer.correct ? 'آفرین! پاسخ درست بود 🎉' : `پاسخ صحیح: ${current.correct_answer || '—'}`}
        </div>
      )}

      {/* Navigation */}
      <div className="flex items-center justify-center gap-2">
        <Button variant="outline" size="sm" className="h-8 px-3 text-xs" disabled={currentIndex === 0} onClick={prev}>
          <ChevronRight className="h-4 w-4 ml-1" />
          قبلی
        </Button>
        <Button variant="outline" size="sm" className="h-8 px-3 text-xs" onClick={next}>
          {currentIndex === total - 1 ? 'پایان' : 'بعدی'}
          <ChevronLeft className="h-4 w-4 mr-1" />
        </Button>
      </div>
    </div>
  );
}
