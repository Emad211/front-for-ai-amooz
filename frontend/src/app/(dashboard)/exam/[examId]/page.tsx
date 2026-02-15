'use client';

import React from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { 
    Bot,
    ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ExamHeader } from '@/components/dashboard/exam/exam-header';
import { QuestionContent } from '@/components/dashboard/exam/question-content';
import { ChatAssistant } from '@/components/dashboard/exam/chat-assistant';
import { Sheet, SheetContent, SheetTrigger, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { ErrorState } from '@/components/shared/error-state';
import { useExam } from '@/hooks/use-exam';
import { useParams } from 'next/navigation';
import { useRouter } from 'next/navigation';

export default function ExamPage() {
    const params = useParams();
    const router = useRouter();
    const rawExamId = (params as any)?.examId as string | string[] | undefined;
    const examId = Array.isArray(rawExamId) ? rawExamId[0] : rawExamId;
    const { exam, currentQuestion, isChatOpen, toggleChat, isLoading, error, isSubmitting, isFinalized, isCheckingAnswer, answers, feedbacks, goToNextQuestion, goToPrevQuestion, submitAnswer, checkAnswer, finalizeExam } = useExam(examId);
    const selectedOptionLabel = currentQuestion ? answers[currentQuestion.id] : undefined;
    const currentFeedback = currentQuestion ? (feedbacks[currentQuestion.id] ?? null) : null;
    const unansweredCount = React.useMemo(() => {
        const list = exam?.questionsList || [];
        return list.filter((q) => !answers[String(q.id)]).length;
    }, [exam?.questionsList, answers]);

    const handleFinalize = React.useCallback(async () => {
        const result = await finalizeExam();
        if (result?.finalized) {
            router.push(`/exam/${examId}/result`);
        }
    }, [finalizeExam, router, examId]);

    if (!examId) {
        return (
            <main className="p-4 md:p-8 max-w-5xl mx-auto">
                <ErrorState title="شناسه آزمون نامعتبر است" description="لطفاً دوباره وارد صفحه آزمون شوید." />
            </main>
        );
    }

    if (isLoading) {
        return <div className="flex items-center justify-center h-screen">در حال بارگذاری...</div>;
    }

    if (error || !exam) {
        return (
            <main className="p-4 md:p-8 max-w-5xl mx-auto">
                <ErrorState title="خطا در دریافت اطلاعات آزمون" description={error || 'اطلاعات آزمون در دسترس نیست.'} />
            </main>
        );
    }

    return (
        <div className="bg-background font-body text-foreground antialiased min-h-screen flex flex-col overflow-hidden">
            {/* Mobile Header */}
            <header className="lg:hidden flex items-center justify-between px-4 py-3 border-b bg-card/50 backdrop-blur-md z-50">
                <div className="flex items-center gap-3">
                    <Link href="/exam-prep">
                        <Button variant="ghost" size="icon" className="rounded-full">
                            <ChevronRight className="h-5 w-5" />
                        </Button>
                    </Link>
                    <div className="flex flex-col">
                        <span className="text-[10px] text-muted-foreground">{exam.title}</span>
                        <span className="text-xs font-bold truncate max-w-[150px]">{exam.subject} - سوال {currentQuestion?.number}</span>
                    </div>
                </div>
                
                <div className="flex items-center gap-2">
                    <Sheet>
                        <SheetTrigger asChild>
                            <Button variant="outline" size="icon" className="rounded-xl h-9 w-9">
                                <Bot className="h-4 w-4" />
                            </Button>
                        </SheetTrigger>
                        <SheetContent side="left" className="!p-0 !w-full !h-full !max-w-none border-none [&>button]:hidden bg-card">
                            <SheetTitle className="sr-only">دستیار حل سوال</SheetTitle>
                            <SheetDescription className="sr-only">چت با هوش مصنوعی برای حل سوالات آزمون</SheetDescription>
                            <ChatAssistant
                                isOpen={true}
                                onToggle={() => {}}
                                isMobile
                                className="!w-full !h-full"
                                examId={examId}
                                question={currentQuestion}
                                selectedOptionLabel={selectedOptionLabel}
                                isChecked={isFinalized}
                            />
                        </SheetContent>
                    </Sheet>
                </div>
            </header>
            <main className="flex-grow w-full max-w-[1920px] mx-auto h-[calc(100dvh-60px)] lg:h-screen flex overflow-hidden relative">
                
                <div className={cn(
                    "flex-1 flex flex-col relative transition-all duration-300 ease-in-out", 
                    isChatOpen ? "lg:w-[calc(100%-36rem)]" : "w-full"
                )}>
                    <ExamHeader title={exam.title} onToggle={toggleChat} />
                    <div className="flex-1 overflow-y-auto">
                        <QuestionContent 
                            question={currentQuestion} 
                            totalQuestions={exam.totalQuestions || 0}
                            onNext={goToNextQuestion}
                            onPrev={goToPrevQuestion}
                            onSubmit={submitAnswer}
                            onCheckAnswer={checkAnswer}
                            onFinalize={handleFinalize}
                            isSubmitting={isSubmitting}
                            isFinalized={isFinalized}
                            isCheckingAnswer={isCheckingAnswer}
                            selectedOptionId={selectedOptionLabel}
                            unansweredCount={unansweredCount}
                            feedback={currentFeedback}
                        />
                    </div>
                </div>

                <ChatAssistant
                    isOpen={isChatOpen}
                    onToggle={toggleChat}
                    examId={examId}
                    question={currentQuestion}
                    selectedOptionLabel={selectedOptionLabel}
                    isChecked={isFinalized}
                />

                {!isChatOpen && (
                     <button 
                        onClick={toggleChat} 
                        className="hidden lg:flex absolute top-1/2 -translate-y-1/2 left-0 h-28 w-10 bg-card/80 backdrop-blur-sm border-y border-l border-border rounded-l-2xl flex-col items-center justify-center text-primary shadow-lg hover:bg-card transition-all group z-50"
                        title="باز کردن دستیار هوشمند"
                    >
                        <ChevronRight className="h-6 w-6 mb-1 transition-transform group-hover:scale-110" />
                        <Bot className="h-6 w-6 transition-transform group-hover:scale-110" />
                    </button>
                )}
                
            </main>
        </div>
    );
}
