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
import { DashboardService } from '@/services/dashboard-service';
import { useProfile } from '@/hooks/use-profile';

export default function LearnPage() {
    const params = useParams();
    const rawCourseId = (params as any)?.courseId as string | string[] | undefined;
    const courseId = Array.isArray(rawCourseId) ? rawCourseId[0] : rawCourseId;
    const { content, currentLesson, isLoading, error, reload, setCurrentLesson, setContent } = useCourseContent(courseId);
    const { user } = useProfile();
    const [isChatOpen, setIsChatOpen] = React.useState(true);
    const [isDownloadingPdf, setIsDownloadingPdf] = React.useState(false);

    const studentName = React.useMemo(() => {
        return String(user?.name ?? '').trim();
    }, [user?.name]);

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

    const chatLessonId = React.useMemo(() => {
        const id = String((currentLesson as any)?.id ?? '').trim();
        return id || null;
    }, [currentLesson]);

    const chatLessonTitle = React.useMemo(() => {
        return String((currentLesson as any)?.title ?? '').trim();
    }, [currentLesson]);

    const chatPageContext = React.useMemo(() => {
        return String((currentLesson as any)?.title ?? '').trim();
    }, [currentLesson]);

    const chatPageMaterial = React.useMemo(() => {
        const lesson: any = currentLesson as any;
        const id = String(lesson?.id ?? '').trim();

        if (/^\d+$/.test(id)) {
            return String(lesson?.content ?? '').trim();
        }

        if (id === 'learning-objectives') {
            const items = (content?.learningObjectives ?? []).map((x) => String(x).trim()).filter(Boolean);
            return items.length ? `# اهداف یادگیری\n\n${items.map((x) => `- ${x}`).join('\n')}` : '';
        }

        if (id === 'prerequisites') {
            const items = (content?.prerequisites ?? []).map((p) => String(p?.name ?? '').trim()).filter(Boolean);
            return items.length ? `# پیشنیازها\n\n${items.map((x) => `- ${x}`).join('\n')}` : '';
        }

        if (id === 'recap') {
            return String(content?.recapMarkdown ?? '').trim();
        }

        if (id.startsWith('prereq:')) {
            return String(lesson?.content ?? '').trim();
        }

        return '';
    }, [content?.learningObjectives, content?.prerequisites, content?.recapMarkdown, currentLesson]);

    const handleDownloadPdf = React.useCallback(async () => {
        try {
            if (!courseId) {
                throw new Error('شناسه کلاس مشخص نیست.');
            }

            if (typeof window === 'undefined') return;
            if (isDownloadingPdf) return;
            setIsDownloadingPdf(true);

            const blob = await DashboardService.downloadCoursePdf(courseId);
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const rawTitle = String(content?.title || 'course').trim() || 'course';
            const safeTitle = rawTitle.replace(/[\\/:*?"<>|]+/g, ' ').trim() || 'course';
            a.download = `${safeTitle}_جزوه.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (e) {
            const msg = e instanceof Error ? e.message : 'خطا در دانلود جزوه';
            // Keep UX minimal: reuse existing alert/toast patterns elsewhere.
            alert(msg);
        } finally {
            setIsDownloadingPdf(false);
        }
    }, [content?.title, courseId, isDownloadingPdf]);

    const allLessons = React.useMemo(() => {
        if (!content) return [];
        return content.chapters.flatMap((c) => c.lessons);
    }, [content]);

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

    // Restore last viewed lesson for repeat entries.
    React.useEffect(() => {
        if (!content) return;
        if (!courseId) return;
        if (typeof window === 'undefined') return;

        const stored = (window.localStorage.getItem(lastLessonKey) || '').trim();
        if (!stored) return;

        // Avoid redundant sets.
        if (currentLesson?.id === stored) return;

        const direct = allLessons.find((l) => l.id === stored);
        if (direct) {
            setCurrentLesson(direct as any);
            return;
        }

        if (stored === 'learning-objectives') {
            setCurrentLesson({ id: 'learning-objectives', title: 'اهداف یادگیری', type: 'text', isSpecial: true } as any);
            return;
        }
        if (stored === 'prerequisites') {
            setCurrentLesson({ id: 'prerequisites', title: 'پیش نیازها', type: 'text', isSpecial: true } as any);
            return;
        }
        if (stored === 'recap') {
            setCurrentLesson({ id: 'recap', title: 'خلاصه و نکات', type: 'text', isSpecial: true } as any);
            return;
        }
        if (stored === 'final-exam') {
            setCurrentLesson({ id: 'final-exam', title: 'آزمون نهایی دوره', type: 'quiz', finalExam: true } as any);
            return;
        }

        if (stored.startsWith('chapter-quiz:')) {
            const chapterId = stored.split(':')[1] ?? '';
            const ch = content.chapters.find((c) => c.id === chapterId);
            if (!ch) return;
            setCurrentLesson({
                id: `chapter-quiz:${chapterId}`,
                title: `آزمون پایان فصل: ${ch.title}`,
                type: 'quiz',
                chapterId,
                isSpecial: true,
            } as any);
            return;
        }

        if (stored.startsWith('prereq-teaching:')) {
            const prereqId = Number(stored.split(':')[1]);
            const prereq = (content.prerequisites || []).find((p) => p.id === prereqId);
            if (!prereq) return;
            setCurrentLesson({
                id: `prereq-teaching:${prereq.id}`,
                title: `آموزش پیش نیاز: ${prereq.name}`,
                type: 'text',
                isSpecial: true,
            } as any);
        }
    }, [allLessons, content, courseId, currentLesson?.id, lastLessonKey, setCurrentLesson]);

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
                                onDownloadPdf={handleDownloadPdf}
                                isDownloadingPdf={isDownloadingPdf}
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
                            <ChatAssistant
                                isOpen={true}
                                onToggle={() => {}}
                                isMobile
                                className="!w-full !h-full"
                                courseId={String(courseId ?? '')}
                                lessonId={chatLessonId}
                                lessonTitle={chatLessonTitle}
                                pageContext={chatPageContext}
                                pageMaterial={chatPageMaterial}
                                studentName={studentName}
                            />
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
                    onDownloadPdf={handleDownloadPdf}
                    isDownloadingPdf={isDownloadingPdf}
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
                        onProgressUpdate={(progress) => {
                            setContent((prev: any) => (prev ? { ...prev, progress } : prev));
                        }}
                    />
                </div>
                <ChatAssistant
                    isOpen={isChatOpen}
                    onToggle={toggleChat}
                    courseId={String(courseId ?? '')}
                    lessonId={chatLessonId}
                    lessonTitle={chatLessonTitle}
                    pageContext={chatPageContext}
                    pageMaterial={chatPageMaterial}
                    studentName={studentName}
                />
                
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
