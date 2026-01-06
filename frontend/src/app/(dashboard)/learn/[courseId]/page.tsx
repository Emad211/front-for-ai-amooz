'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import { 
    Bot,
    ChevronLeft,
    List,
    ChevronRight
} from 'lucide-react';
import { cn } from '@/lib/utils';
import '../learn.css';
import { CourseSidebar } from '@/components/dashboard/learn/course-sidebar';
import { LessonContent } from '@/components/dashboard/learn/lesson-content';
import { ChatAssistant } from '@/components/dashboard/learn/learn-chat-assistant';
import { Sheet, SheetContent, SheetTrigger, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import Link from 'next/link';
import { useCourseContent } from '@/hooks/use-course-content';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState } from '@/components/shared/error-state';

export default function LearnPage() {
    const params = useParams();
    const rawCourseId = (params as any)?.courseId as string | string[] | undefined;
    const courseId = Array.isArray(rawCourseId) ? rawCourseId[0] : rawCourseId;
    const { content, currentLesson, isLoading, error, reload, setCurrentLesson } = useCourseContent(courseId);
    const [isChatOpen, setIsChatOpen] = React.useState(true);

    const lastLessonKey = React.useMemo(() => `ai_amooz_course_last_lesson_${String(courseId ?? '')}`, [courseId]);
    const visitedKey = React.useMemo(() => `ai_amooz_course_visited_${String(courseId ?? '')}`, [courseId]);

    const persistCurrentLessonId = React.useCallback(
        (lessonId: string) => {
            if (typeof window === 'undefined') return;
            const id = String(lessonId ?? '').trim();
            if (!id) return;
            window.localStorage.setItem(lastLessonKey, id);
            window.localStorage.setItem(visitedKey, '1');
        },
        [lastLessonKey, visitedKey]
    );

    // Mark as visited on entry.
    React.useEffect(() => {
        if (typeof window === 'undefined') return;
        if (!courseId) return;
        window.localStorage.setItem(visitedKey, '1');
    }, [courseId, visitedKey]);

    const toggleChat = () => setIsChatOpen(!isChatOpen);

    if (isLoading) {
        return (
            <div className="h-screen flex items-center justify-center bg-background">
                <div className="flex flex-col items-center gap-4">
                    <Skeleton className="h-12 w-12 rounded-full" />
                    <Skeleton className="h-4 w-48" />
                </div>
            </div>
        );
    }

    if (error || !content) {
        const title = error ? 'خطا در دریافت محتوا' : 'محتوا یافت نشد';
        const description = error || 'محتوای این دوره در دسترس نیست.';
        return (
            <div className="h-screen flex items-center justify-center bg-background">
                <div className="w-full max-w-2xl px-4">
                    <ErrorState
                        title={title}
                        description={description}
                        variant={error ? 'error' : 'not-found'}
                        onRetry={reload}
                        primaryAction={{ label: 'بازگشت به کلاس‌ها', href: '/classes' }}
                        secondaryAction={{ label: 'خانه', href: '/home' }}
                    />
                </div>
            </div>
        );
    }

    const allLessons = content.chapters.flatMap((c) => c.lessons);

    // Default behavior on first entry: open learning objectives.
    React.useEffect(() => {
        if (!content) return;
        if (!courseId) return;
        if (typeof window === 'undefined') return;

        const stored = (window.localStorage.getItem(lastLessonKey) || '').trim();
        if (stored) return;

        setCurrentLesson({
            id: 'learning-objectives',
            title: 'اهداف یادگیری',
            type: 'text',
            isSpecial: true,
        } as any);
        persistCurrentLessonId('learning-objectives');
    }, [content, courseId, lastLessonKey, persistCurrentLessonId, setCurrentLesson]);

    const handleSelectLesson = (lessonId: string) => {
        const lesson = allLessons.find((l) => l.id === lessonId) ?? null;
        if (lesson) {
            setCurrentLesson(lesson as any);
            persistCurrentLessonId(lesson.id);
        }
    };

    const handleSelectChapterQuiz = (chapterId: string) => {
        const ch = content.chapters.find((c) => c.id === chapterId);
        if (!ch) return;
        const next = {
            id: `chapter-quiz:${ch.id}`,
            title: 'آزمون فصل',
            type: 'quiz',
            chapterId: ch.id,
            chapterTitle: ch.title,
        } as any;
        setCurrentLesson(next);
        persistCurrentLessonId(next.id);
    };

    const handleSelectFinalExam = () => {
        const next = {
            id: 'final-exam',
            title: 'آزمون نهایی دوره',
            type: 'quiz',
            finalExam: true,
        } as any;
        setCurrentLesson(next);
        persistCurrentLessonId(next.id);
    };

    const handleSelectLearningObjectives = () => {
        const next = {
            id: 'learning-objectives',
            title: 'اهداف یادگیری',
            type: 'text',
            isSpecial: true,
        } as any;
        setCurrentLesson(next);
        persistCurrentLessonId(next.id);
    };

    const handleSelectPrerequisites = () => {
        const next = {
            id: 'prerequisites',
            title: 'پیش نیازها',
            type: 'text',
            isSpecial: true,
        } as any;
        setCurrentLesson(next);
        persistCurrentLessonId(next.id);
    };

    const handleSelectRecap = () => {
        const next = {
            id: 'recap',
            title: 'خلاصه و نکات',
            type: 'text',
            isSpecial: true,
        } as any;
        setCurrentLesson(next);
        persistCurrentLessonId(next.id);
    };

    const handleSelectPrerequisiteTeaching = (prereqId: number) => {
        const prereq = content.prerequisites?.find((p) => p.id === prereqId);
        if (!prereq) return;
        const next = {
            id: `prereq:${prereq.id}`,
            title: prereq.name,
            type: 'text',
            isSpecial: true,
            content: prereq.teaching_text || '',
        } as any;
        setCurrentLesson(next);
        persistCurrentLessonId(next.id);
    };

    return (
        <div className="bg-background font-body text-foreground antialiased min-h-screen flex flex-col overflow-hidden">
            {/* Mobile Header */}
            <header className="lg:hidden flex items-center justify-between px-4 py-3 border-b bg-card/50 backdrop-blur-md z-50">
                <div className="flex items-center gap-3">
                    <Link href="/classes">
                        <Button variant="ghost" size="icon" className="rounded-full">
                            <ChevronRight className="h-5 w-5" />
                        </Button>
                    </Link>
                    <div className="flex flex-col">
                        <span className="text-[10px] text-muted-foreground">{content.title}</span>
                        <span className="text-xs font-bold truncate max-w-[150px]">{currentLesson?.title}</span>
                    </div>
                </div>
                
                <div className="flex items-center gap-2">
                    <Sheet>
                        <SheetTrigger asChild>
                            <Button variant="outline" size="icon" className="rounded-xl h-9 w-9">
                                <List className="h-4 w-4" />
                            </Button>
                        </SheetTrigger>
                        <SheetContent side="right" className="!p-0 !w-full !h-full !max-w-none border-none [&>button]:hidden bg-background">
                            <SheetTitle className="sr-only">لیست دروس</SheetTitle>
                            <SheetDescription className="sr-only">نمایش سرفصل‌ها و دروس دوره</SheetDescription>
                            <CourseSidebar
                                content={content}
                                className="w-full h-full border-none flex"
                                isMobile
                                activeLessonId={currentLesson?.id ?? null}
                                onSelectLesson={handleSelectLesson}
                                onSelectChapterQuiz={handleSelectChapterQuiz}
                                onSelectFinalExam={handleSelectFinalExam}
                                onSelectLearningObjectives={handleSelectLearningObjectives}
                                onSelectPrerequisites={handleSelectPrerequisites}
                                onSelectRecap={handleSelectRecap}
                            />
                        </SheetContent>
                    </Sheet>

                    <Sheet>
                        <SheetTrigger asChild>
                            <Button variant="outline" size="icon" className="rounded-xl h-9 w-9">
                                <Bot className="h-4 w-4" />
                            </Button>
                        </SheetTrigger>
                        <SheetContent side="left" className="!p-0 !w-full !h-full !max-w-none border-none [&>button]:hidden bg-card">
                            <SheetTitle className="sr-only">دستیار هوشمند</SheetTitle>
                            <SheetDescription className="sr-only">چت با هوش مصنوعی برای رفع اشکال</SheetDescription>
                            <ChatAssistant isOpen={true} onToggle={() => {}} isMobile className="!w-full !h-full" />
                        </SheetContent>
                    </Sheet>
                </div>
            </header>
            <main className="flex-grow w-full max-w-[1920px] mx-auto lg:p-4 h-[calc(100dvh-60px)] lg:h-screen flex gap-4 overflow-hidden relative">
                <CourseSidebar 
                    content={content}
                    activeLessonId={currentLesson?.id ?? null}
                    onSelectLesson={handleSelectLesson}
                    onSelectChapterQuiz={handleSelectChapterQuiz}
                    onSelectFinalExam={handleSelectFinalExam}
                    onSelectLearningObjectives={handleSelectLearningObjectives}
                    onSelectPrerequisites={handleSelectPrerequisites}
                    onSelectRecap={handleSelectRecap}
                />
                <div className={cn(
                    "flex-1 flex flex-col relative transition-all duration-300 ease-in-out", 
                    isChatOpen ? "lg:w-[calc(100%-20rem-24rem)]" : "w-full"
                )}>
                    <LessonContent
                        content={content}
                        lesson={currentLesson}
                        courseId={String(courseId ?? '')}
                        onSelectPrerequisiteTeaching={handleSelectPrerequisiteTeaching}
                        onBackToPrerequisites={handleSelectPrerequisites}
                    />
                </div>
                <ChatAssistant isOpen={isChatOpen} onToggle={toggleChat} />
                
                {!isChatOpen && (
                     <button 
                        onClick={toggleChat} 
                        className="hidden lg:flex absolute top-1/2 -translate-y-1/2 left-0 h-28 w-10 bg-card/80 backdrop-blur-sm border-y border-l border-border rounded-l-2xl flex-col items-center justify-center text-primary shadow-lg hover:bg-card transition-all group z-50"
                        title="باز کردن دستیار هوشمند"
                    >
                        <ChevronLeft className="h-6 w-6 mb-1 transition-transform group-hover:scale-110" />
                        <Bot className="h-6 w-6 transition-transform group-hover:scale-110" />
                    </button>
                )}
            </main>
        </div>
    );
}
