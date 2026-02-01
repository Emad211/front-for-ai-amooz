'use client';

import { Button } from '@/components/ui/button';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Question } from '@/types';

interface QuestionContentProps {
  question: Question | null;
  totalQuestions: number;
  onNext: () => void;
  onPrev: () => void;
  onSubmit: (questionId: string, answerId: string) => void;
  onFinalize: () => void;
  isSubmitting?: boolean;
}

export const QuestionContent = ({ question, totalQuestions, onNext, onPrev, onSubmit, onFinalize, isSubmitting }: QuestionContentProps) => {
  if (!question) return null;

  return (
    <section className="flex-1 flex flex-col justify-center items-center gap-8 p-4 sm:p-6 md:p-8 w-full min-h-full">
      <div className="bg-card border border-border rounded-2xl p-4 sm:p-6 shadow-lg flex flex-col w-full max-w-4xl my-auto">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold text-primary">سوال {question.number}</h2>
            <span className="text-xs font-semibold text-muted-foreground bg-secondary px-2 py-1 rounded-md">
              {question.number} / {totalQuestions}
            </span>
          </div>
        </div>
        <div className="space-y-6 flex-grow">
          <p className="text-foreground leading-8 text-base sm:text-lg text-right">
            {question.text}
          </p>
          <RadioGroup 
            defaultValue={question.userAnswerId} 
            onValueChange={(value) => onSubmit(question.id, value)}
            dir="rtl" 
            className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4"
            disabled={Boolean(isSubmitting)}
          >
            {question.options.map((option) => (
              <Label
                key={option.id}
                htmlFor={`option-${option.id}`}
                className="flex items-center justify-between p-3 sm:p-4 bg-background border border-border rounded-lg cursor-pointer hover:bg-secondary/50 has-[:checked]:bg-primary/10 has-[:checked]:border-primary"
              >
                <div className="flex items-center gap-3">
                  <RadioGroupItem value={option.id} id={`option-${option.id}`} />
                  <span className="text-sm sm:text-base">{option.label})</span>
                  <span className="font-mono text-sm sm:text-base">{option.text}</span>
                </div>
              </Label>
            ))}
          </RadioGroup>
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
          <Button
            size="lg"
            className="w-full sm:w-auto bg-primary text-primary-foreground hover:bg-primary/90"
            onClick={onFinalize}
            disabled={Boolean(isSubmitting)}
          >
            {isSubmitting ? 'در حال ثبت...' : 'ثبت پاسخ و پایان آزمون'}
            <ChevronLeft className="mr-2 h-4 w-4" />
          </Button>
        </div>
      </div>
    </section>
  );
};
