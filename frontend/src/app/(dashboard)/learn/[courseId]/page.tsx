'use client';

import React from 'react';
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

export default function LearnPage() {
    const [isChatOpen, setIsChatOpen] = React.useState(true);

    const toggleChat = () => setIsChatOpen(!isChatOpen);

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
                        <span className="text-[10px] text-muted-foreground">دوره آموزش جامع</span>
                        <span className="text-xs font-bold truncate max-w-[150px]">درس اول: مقدمات</span>
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
                            <CourseSidebar className="w-full h-full border-none flex" isMobile />
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
            <main className="flex-grow w-full max-w-[1920px] mx-auto lg:p-4 h-[calc(100vh-60px)] lg:h-screen flex gap-4 overflow-hidden relative">
                <CourseSidebar />
                <div className={cn(
                    "flex-1 flex flex-col relative transition-all duration-300 ease-in-out", 
                    isChatOpen ? "lg:w-[calc(100%-20rem-24rem)]" : "w-full"
                )}>
                    <LessonContent />
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
