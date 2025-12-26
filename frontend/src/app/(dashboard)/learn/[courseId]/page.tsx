'use client';

import React from 'react';
import { 
    Bot,
    ChevronLeft,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import '../learn.css';
import { CourseSidebar } from '@/components/dashboard/learn/course-sidebar';
import { LessonContent } from '@/components/dashboard/learn/lesson-content';
import { ChatAssistant } from '@/components/dashboard/learn/learn-chat-assistant';

export default function LearnPage() {
    const [isChatOpen, setIsChatOpen] = React.useState(true);

    const toggleChat = () => setIsChatOpen(!isChatOpen);

    return (
        <div className="bg-background font-body text-foreground antialiased min-h-screen flex flex-col overflow-hidden">
            <main className="flex-grow w-full max-w-[1920px] mx-auto p-4 h-screen flex gap-4 overflow-hidden relative">
                <CourseSidebar />
                <div className={cn("flex-1 flex flex-col relative transition-all duration-300 ease-in-out", isChatOpen ? "w-[calc(100%-20rem-24rem)]" : "w-full")}>
                    <LessonContent />
                </div>
                <ChatAssistant isOpen={isChatOpen} onToggle={toggleChat} />
                
                {!isChatOpen && (
                     <button 
                        onClick={toggleChat} 
                        className="absolute top-1/2 -translate-y-1/2 left-0 h-28 w-10 bg-card/80 backdrop-blur-sm border-y border-l border-border rounded-l-2xl flex flex-col items-center justify-center text-primary shadow-lg hover:bg-card transition-all group z-50"
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
