'use client';

import React from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { 
    ArrowLeft, 
    Bot,
    Paperclip,
    Mic,
    Send,
    PanelRightClose,
    ChevronLeft,
    ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"
import { ExamHeader } from '@/components/dashboard/exam/exam-header';
import { QuestionContent } from '@/components/dashboard/exam/question-content';
import { ChatAssistant } from '@/components/dashboard/exam/chat-assistant';


export default function ExamPage() {
    const [isChatOpen, setIsChatOpen] = React.useState(true);

    const toggleChat = () => setIsChatOpen(!isChatOpen);

    return (
        <div className="bg-background font-body text-foreground antialiased min-h-screen flex flex-col overflow-hidden">
            <main className="flex-grow w-full max-w-[1920px] mx-auto h-screen flex overflow-hidden relative">
                
                <div className={cn("flex-1 flex flex-col relative transition-all duration-300 ease-in-out", isChatOpen ? "w-[calc(100%-36rem)]" : "w-full")}>
                    <ExamHeader onToggle={toggleChat} />
                    <div className="flex-1 overflow-y-auto">
                        <QuestionContent />
                    </div>
                </div>

                <ChatAssistant isOpen={isChatOpen} onToggle={toggleChat} />

                {!isChatOpen && (
                     <button 
                        onClick={toggleChat} 
                        className="absolute top-1/2 -translate-y-1/2 left-0 h-28 w-10 bg-card/80 backdrop-blur-sm border-y border-l border-border rounded-l-2xl flex flex-col items-center justify-center text-primary shadow-lg hover:bg-card transition-all group z-50"
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
