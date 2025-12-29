'use client';

import { BarChart, Signal, Clock, PlayCircle } from 'lucide-react';
import { CourseContent } from '@/constants/mock/course-content-data';

interface LessonContentProps {
  content: CourseContent;
  lesson: any;
}

export const LessonContent = ({ content, lesson }: LessonContentProps) => (
  <section className="flex-1 flex flex-col gap-3 overflow-y-auto no-scrollbar h-full rounded-2xl relative">
    <div className="bg-card border border-border rounded-2xl p-4 shadow-lg relative overflow-hidden flex-shrink-0">
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="text-lg font-bold text-foreground mb-1">{content.title}</h1>
          <p className="text-sm text-muted-foreground leading-relaxed line-clamp-1">
            {content.description}
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-y-3 gap-x-2 text-xs sm:text-sm text-muted-foreground border-t border-border pt-3">
          <div className="flex items-center gap-2">
            <BarChart className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-primary" />
            <span>
              تکمیل: <span className="font-bold text-foreground">{content.progress}٪</span>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Signal className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-primary" />
            <span>
              سطح: <span className="font-bold text-foreground">{content.level}</span>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-primary" />
            <span>
              زمان: <span className="font-bold text-foreground">{content.duration}</span>
            </span>
          </div>
        </div>
      </div>
    </div>
    <div className="bg-card border border-border rounded-2xl p-6 sm:p-8 flex-1 shadow-xl overflow-y-auto no-scrollbar">
      <div className="flex items-center gap-3 mb-6 pb-3 border-b border-border/50">
        <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
          <PlayCircle className="h-5 w-5" />
        </div>
        <h2 className="text-lg font-bold text-foreground">{lesson?.title}</h2>
      </div>
      <div className="prose prose-invert max-w-none text-muted-foreground leading-relaxed space-y-6">
        <div className="text-justify whitespace-pre-line">
          {lesson?.content}
        </div>

        {lesson?.formulas && (
          <div className="bg-card/50 border border-border/50 rounded-xl p-6 my-6">
            <h3 className="text-foreground font-bold mb-4 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-primary"></span>
              فرمول‌های کلیدی
            </h3>
            <div className="space-y-4">
              {lesson.formulas.map((f: any, i: number) => (
                <div key={i} className="flex items-center justify-between bg-background/50 p-3 rounded-lg border border-border/30">
                  <span>{f.label}</span>
                  <code className="text-primary font-mono text-lg" dir="ltr">{f.formula}</code>
                </div>
              ))}
            </div>
          </div>
        )}

        {lesson?.tips && lesson.tips.map((tip: string, i: number) => (
          <div key={i} className="mt-8 p-4 bg-primary/5 border-r-4 border-primary rounded-l-lg italic">
            {tip}
          </div>
        ))}
      </div>
    </div>
  </section>
);
