'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft,
  List,
  Flag,
  Hourglass,
  Folder,
  FolderOpen,
  FileText,
  PlayCircle,
  CheckCircle,
  BookOpen,
  Settings,
  RotateCcw,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { SidebarItem, SubmenuItem } from './sidebar-items';
import { SheetClose } from '@/components/ui/sheet';
import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import type { CourseContent } from '@/types';

interface CourseSidebarProps {
  className?: string;
  isMobile?: boolean;
  content: CourseContent;
  activeLessonId?: string | null;
  onSelectLesson?: (lessonId: string) => void;
  onSelectChapterQuiz?: (chapterId: string) => void;
  onSelectFinalExam?: () => void;
  onSelectLearningObjectives?: () => void;
  onSelectPrerequisites?: () => void;
  onSelectRecap?: () => void;
  onDownloadPdf?: () => void;
  isDownloadingPdf?: boolean;
}

const ICON_MAP = {
  video: PlayCircle,
  text: FileText,
  quiz: CheckCircle,
};

export const CourseSidebar = ({
  className,
  isMobile = false,
  content,
  activeLessonId,
  onSelectLesson,
  onSelectChapterQuiz,
  onSelectFinalExam,
  onSelectLearningObjectives,
  onSelectPrerequisites,
  onSelectRecap,
  onDownloadPdf,
  isDownloadingPdf = false,
}: CourseSidebarProps) => (
  <aside className={cn("w-80 flex-shrink-0 flex-col gap-3 hidden lg:flex h-full", className)}>
    {isMobile ? (
      <SheetClose asChild>
        <Button
          variant="ghost"
          className="bg-secondary/50 hover:bg-secondary border border-border/50 text-foreground rounded-xl p-3 flex items-center justify-between transition-all group h-12"
        >
          <span className="text-sm font-medium pr-1">بستن فهرست</span>
          <X className="h-5 w-5 text-muted-foreground group-hover:text-foreground transition-all" />
        </Button>
      </SheetClose>
    ) : (
      <Button
        variant="outline"
        asChild
        className="bg-card hover:bg-card/80 border-border text-muted-foreground hover:text-foreground rounded-xl p-3 flex items-center justify-between transition-all group h-12"
      >
        <Link href="/classes">
          <span className="text-sm font-medium pr-1">بازگشت به لیست دوره‌ها</span>
          <ArrowLeft className="text-muted-foreground group-hover:text-foreground group-hover:-translate-x-1 transition-all h-5 w-5" />
        </Link>
      </Button>
    )}
    <div className="flex-1 bg-card border border-border rounded-2xl flex flex-col overflow-hidden shadow-lg">
      <div className="p-4 border-b border-border/50 flex items-center justify-between">
        <h3 className="font-bold text-foreground text-sm flex items-center gap-2">
          <List className="text-primary h-5 w-5" />
          فهرست مطالب
        </h3>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1 no-scrollbar">
        <SidebarItem icon={<Flag className="h-5 w-5" />} title="اهداف یادگیری" active={activeLessonId === 'learning-objectives'} onClick={onSelectLearningObjectives} />
        <SidebarItem icon={<Hourglass className="h-5 w-5" />} title="پیش نیازها" active={activeLessonId === 'prerequisites'} onClick={onSelectPrerequisites} />

        <Accordion type="single" collapsible defaultValue={content.chapters[0]?.id} className="w-full">
          {content.chapters.map((chapter) => (
            <AccordionItem key={chapter.id} value={chapter.id} className="border-none">
              <AccordionTrigger className="p-3 rounded-xl hover:no-underline hover:bg-secondary/30 text-foreground data-[state=open]:font-bold data-[state=open]:border data-[state=open]:border-border group">
                <div className="flex items-center gap-3">
                  <Folder className="h-5 w-5 group-data-[state=open]:hidden" />
                  <FolderOpen className="h-5 w-5 hidden group-data-[state=open]:block" />
                  <span className="text-sm"><MarkdownWithMath markdown={chapter.title} /></span>
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-1 space-y-1">
                {chapter.lessons.map((lesson) => {
                  const Icon = ICON_MAP[lesson.type as keyof typeof ICON_MAP] || FileText;
                  return (
                    <SubmenuItem 
                      key={lesson.id}
                      icon={<Icon className="h-4 w-4" />} 
                      title={lesson.title} 
                      active={(activeLessonId ? lesson.id === activeLessonId : !!lesson.isActive)}
                      special={lesson.isSpecial}
                      onClick={() => onSelectLesson?.(lesson.id)}
                    />
                  );
                })}

                <SubmenuItem
                  key={`chapter-quiz:${chapter.id}`}
                  icon={<CheckCircle className="h-4 w-4" />}
                  title="آزمون فصل"
                  active={activeLessonId ? activeLessonId === `chapter-quiz:${chapter.id}` : false}
                  onClick={() => onSelectChapterQuiz?.(chapter.id)}
                />
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>

        <SidebarItem
          icon={<CheckCircle className="h-5 w-5" />}
          title="آزمون نهایی دوره"
          active={activeLessonId === 'final-exam'}
          onClick={onSelectFinalExam}
        />
        <SidebarItem
          icon={<BookOpen className="h-5 w-5" />}
          title="خلاصه و نکات"
          active={activeLessonId === 'recap'}
          onClick={onSelectRecap}
        />
      </div>
      <div className="p-3 border-t border-border/50 space-y-2 bg-background/20">
        <Button
          variant="outline"
          className="w-full justify-between p-2.5 h-auto bg-secondary/50 border-border text-primary hover:bg-primary/10 hover:border-primary/30 transition-all"
          onClick={onDownloadPdf}
          disabled={!onDownloadPdf || isDownloadingPdf}
        >
          <span className="text-sm font-bold">{isDownloadingPdf ? 'در حال ساخت جزوه…' : 'دانلود جزوه'}</span>
          <BookOpen className="h-4 w-4" />
        </Button>
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="flex-1 justify-center gap-2 p-2.5 h-auto bg-secondary/50 border-border text-muted-foreground hover:text-foreground hover:bg-secondary"
          >
            <span className="text-sm font-medium">تنظیمات</span>
            <Settings className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            className="flex-1 justify-center gap-2 p-2.5 h-auto bg-secondary/50 border-border text-muted-foreground hover:text-foreground hover:bg-secondary"
          >
            <span className="text-sm font-medium">شروع مجدد</span>
            <RotateCcw className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  </aside>
);
