'use client';

import React from 'react';
import { BarChart, Signal, Clock, PlayCircle } from 'lucide-react';
import type { CourseContent } from '@/types';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { ChapterQuiz } from './chapter-quiz';
import { FinalExam } from './final-exam';
import { Button } from '@/components/ui/button';

interface LessonContentProps {
  content: CourseContent;
  lesson: any;
  courseId?: string;
  onSelectPrerequisiteTeaching?: (prereqId: number) => void;
  onBackToPrerequisites?: () => void;
  onProgressUpdate?: (progress: number) => void;
}

export const LessonContent = ({
  content,
  lesson,
  courseId,
  onSelectPrerequisiteTeaching,
  onBackToPrerequisites,
  onProgressUpdate,
}: LessonContentProps) => {
  const [visiblePrereqCount, setVisiblePrereqCount] = React.useState(3);

  React.useEffect(() => {
    if (lesson?.id === 'prerequisites') setVisiblePrereqCount(3);
  }, [lesson?.id]);

  const objectivesMarkdown = React.useMemo(() => {
    const objectives = content.learningObjectives ?? [];
    if (!objectives.length) return 'فعلاً هدف یادگیری برای این دوره ثبت نشده است.';
    return objectives.map((t) => `- ${t}`).join('\n');
  }, [content.learningObjectives]);

  const prerequisites = content.prerequisites ?? [];
  const visiblePrereqs = prerequisites.slice(0, Math.max(0, visiblePrereqCount));

  const prereqTeaching = React.useMemo(() => {
    const id = String(lesson?.id ?? '');
    if (!id.startsWith('prereq:')) return null;
    const raw = id.split(':')[1] ?? '';
    const prereqId = Number(raw);
    if (!Number.isFinite(prereqId)) return null;
    const index = prerequisites.findIndex((p) => p.id === prereqId);
    if (index < 0) return null;
    return { prereqId, index };
  }, [lesson?.id, prerequisites]);

  const recapMarkdown = (content.recapMarkdown ?? '').trim();

  return (
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
        {lesson?.type === 'quiz' && lesson?.chapterId && courseId ? (
          <ChapterQuiz
            courseId={courseId}
            chapterId={lesson.chapterId}
            chapterTitle={lesson.chapterTitle ?? ''}
            onProgressUpdate={onProgressUpdate}
          />
        ) : lesson?.type === 'quiz' && lesson?.finalExam && courseId ? (
          <FinalExam courseId={courseId} onProgressUpdate={onProgressUpdate} />
        ) : lesson?.id === 'learning-objectives' ? (
          <div className="text-justify">
            <MarkdownWithMath markdown={objectivesMarkdown} />
          </div>
        ) : lesson?.id === 'prerequisites' ? (
          <div className="space-y-3">
            {visiblePrereqs.length ? (
              <div className="space-y-2">
                {visiblePrereqs.map((p) => (
                  <Button
                    key={p.id}
                    type="button"
                    variant="outline"
                    className="w-full justify-between h-auto py-3 px-4 rounded-xl"
                    onClick={() => onSelectPrerequisiteTeaching?.(p.id)}
                  >
                    <div className="text-right flex-1">
                      <MarkdownWithMath markdown={p.name} className="text-sm leading-6" />
                    </div>
                    <span className="text-xs text-muted-foreground mr-3">آموزش</span>
                  </Button>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">فعلاً پیش‌نیازی برای این دوره ثبت نشده است.</p>
            )}

            {visiblePrereqCount < prerequisites.length && (
              <Button
                type="button"
                variant="secondary"
                className="w-full rounded-xl"
                onClick={() => setVisiblePrereqCount((n) => Math.min(prerequisites.length, n + 1))}
              >
                بیشتر
              </Button>
            )}
          </div>
        ) : lesson?.id === 'recap' ? (
          <div className="text-justify">
            <MarkdownWithMath
              markdown={recapMarkdown || 'خلاصه این دوره هنوز آماده نیست.'}
            />
          </div>
        ) : (
          <div className="space-y-4">
            {prereqTeaching && (
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <Button
                  type="button"
                  variant="outline"
                  className="rounded-xl"
                  disabled={prereqTeaching.index <= 0}
                  onClick={() => {
                    const prev = prerequisites[prereqTeaching.index - 1];
                    if (prev) onSelectPrerequisiteTeaching?.(prev.id);
                  }}
                >
                  قبلی
                </Button>

                <Button
                  type="button"
                  variant="secondary"
                  className="rounded-xl"
                  onClick={() => onBackToPrerequisites?.()}
                >
                  بازگشت به پیشنیازها
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  className="rounded-xl"
                  disabled={prereqTeaching.index >= prerequisites.length - 1}
                  onClick={() => {
                    const next = prerequisites[prereqTeaching.index + 1];
                    if (next) onSelectPrerequisiteTeaching?.(next.id);
                  }}
                >
                  بعدی
                </Button>
              </div>
            )}

            <div className="text-justify">
              <MarkdownWithMath
                markdown={lesson?.content || (String(lesson?.id ?? '').startsWith('prereq:') ? 'هنوز محتوای آموزشی این پیشنیاز آماده نیست.' : '')}
              />
            </div>
          </div>
        )}

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
};
