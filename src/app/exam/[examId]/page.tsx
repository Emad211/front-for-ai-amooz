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
    PanelLeftClose,
    ChevronRight,
    ChevronLeft,
    HelpCircle
} from 'lucide-react';
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "@/components/ui/accordion"
import { cn } from '@/lib/utils';
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"


const ExamHeader = () => (
    <header className="flex items-center justify-between p-4 border-b border-border w-full">
        <Button variant="outline" asChild className="bg-card hover:bg-card/80 border-border text-muted-foreground hover:text-foreground rounded-xl p-3 flex items-center justify-between transition-all group h-12">
             <Link href="/exam-prep">
                <span className="text-sm font-medium pr-1">بازگشت</span>
                <ArrowLeft className="text-muted-foreground group-hover:text-foreground group-hover:-translate-x-1 transition-all h-5 w-5" />
            </Link>
        </Button>
        <div className="text-center">
            <h1 className="text-xl font-bold text-foreground">بررسی کنکور تیر 1403 - ریاضی</h1>
        </div>
        <div className="bg-card border border-border text-foreground font-semibold px-4 py-2 rounded-lg">
            سوال ۱ از ۱۱
        </div>
    </header>
);

const QuestionContent = () => (
    <section className="flex-1 flex flex-col gap-8 p-4 sm:p-6 md:p-8">
        <div className="bg-card border border-border rounded-2xl p-6 shadow-lg">
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold text-primary">سوال ۱</h2>
            </div>
            <div className="space-y-6">
                <p className="text-foreground leading-8 text-lg text-right">
                    اگر ۱, 2x - 1, x + 1, x² + x و x⁴ به ترتیب جملات چهارم، پنجم، هفتم و هشتم یک دنباله هندسی باشند، حاصل ضرب مقادیر ممکن برای قدر نسبت این دنباله کدام است؟
                </p>
                <RadioGroup defaultValue="c" className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Label htmlFor="option-a" className="flex items-center justify-between p-4 bg-background border border-border rounded-lg cursor-pointer hover:bg-secondary/50 has-[:checked]:bg-primary/10 has-[:checked]:border-primary">
                        <span className="font-mono">۱</span>
                        <div className="flex items-center gap-3">
                           <span>A</span>
                           <RadioGroupItem value="a" id="option-a" />
                        </div>
                    </Label>
                    <Label htmlFor="option-b" className="flex items-center justify-between p-4 bg-background border border-border rounded-lg cursor-pointer hover:bg-secondary/50 has-[:checked]:bg-primary/10 has-[:checked]:border-primary">
                        <span className="font-mono">-۱</span>
                         <div className="flex items-center gap-3">
                           <span>B</span>
                           <RadioGroupItem value="b" id="option-b" />
                        </div>
                    </Label>
                    <Label htmlFor="option-c" className="flex items-center justify-between p-4 bg-background border border-border rounded-lg cursor-pointer hover:bg-secondary/50 has-[:checked]:bg-primary/10 has-[:checked]:border-primary">
                        <span className="font-mono">۲</span>
                         <div className="flex items-center gap-3">
                           <span>C</span>
                           <RadioGroupItem value="c" id="option-c" />
                        </div>
                    </Label>
                    <Label htmlFor="option-d" className="flex items-center justify-between p-4 bg-background border border-border rounded-lg cursor-pointer hover:bg-secondary/50 has-[:checked]:bg-primary/10 has-[:checked]:border-primary">
                        <span className="font-mono">-۲</span>
                         <div className="flex items-center gap-3">
                           <span>D</span>
                           <RadioGroupItem value="d" id="option-d" />
                        </div>
                    </Label>
                </RadioGroup>
            </div>
            <div className="mt-6 flex justify-end">
                <Button size="lg" className="bg-primary text-primary-foreground hover:bg-primary/90">ثبت پاسخ</Button>
            </div>
        </div>

        <div className="flex items-center justify-between">
            <Button variant="outline">
                <ChevronRight className="ml-2 h-4 w-4" />
                قبلی
            </Button>
            <div className="flex items-center gap-1">
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11].map(i => (
                    <Button key={i} size="icon" variant={i === 1 ? 'default' : 'outline'} className={cn("h-9 w-9 rounded-full", i === 1 ? "bg-primary" : "bg-card")}>
                        {i}
                    </Button>
                ))}
            </div>
            <Button>
                بعدی
                <ChevronLeft className="mr-2 h-4 w-4" />
            </Button>
        </div>
    </section>
);


const ChatAssistant = ({ onToggle, isOpen }) => {
    const [message, setMessage] = React.useState('');
    const textareaRef = React.useRef<HTMLTextAreaElement>(null);

    const handleInputChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
        setMessage(event.target.value);
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
        }
    };

    return (
     <aside className={cn(
        "flex-shrink-0 flex-col bg-card border-r border-border rounded-l-2xl overflow-hidden shadow-xl h-full hidden md:flex transition-all duration-300 ease-in-out",
        isOpen ? "w-96" : "w-0 p-0 border-none"
     )}>
        <div className={cn("p-3 border-b border-border flex items-center justify-between bg-secondary/30 backdrop-blur-sm h-[73px]", !isOpen && "hidden")}>
            <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-primary/20 to-purple-500/20 flex items-center justify-center relative ring-1 ring-foreground/10">
                    <Bot className="text-primary h-5 w-5" />
                    <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 bg-green-500 rounded-full border-2 border-card"></span>
                </div>
                <div>
                    <h3 className="text-sm font-bold text-foreground">دستیار حل سوال</h3>
                </div>
            </div>
            <Button onClick={onToggle} variant="ghost" size="icon" className="h-8 w-8 rounded-lg text-muted-foreground hover:text-foreground">
                <PanelLeftClose className="h-4 w-4" />
            </Button>
        </div>
        <div className={cn("flex-1 overflow-y-auto p-4 space-y-6 bg-background/30 no-scrollbar", !isOpen && "hidden")}>
            <ChatMessage sender="ai" time="۱۰:۳۲" message="سلام! 👋 من دستیار حل سوالت هستم.<br/>میتونی سوالت رو بخونی، گزینه انتخاب کنی، یا اگه جایی گیر کردی ازم راهنمایی بخوای. اگه روی کاغذ حل کردی، عکسش رو بفرست تا بررسی کنم." />
        </div>
        <div className={cn("p-3 border-t border-border bg-card z-10", !isOpen && "hidden")}>
             <div className="flex gap-2 mb-2">
                <Button variant="outline" className="text-xs h-8">راهنماییم کن</Button>
                <Button variant="outline" className="text-xs h-8">اشتباهم کجاست؟</Button>
                <Button variant="outline" className="text-xs h-8">به قدم اول بده</Button>
            </div>
            <div className="relative">
                <Textarea 
                    ref={textareaRef}
                    value={message}
                    onChange={handleInputChange}
                    placeholder="سوالت رو بپرس... یا تصویر حل دستیت رو بفرست" 
                    rows={1}
                    className="bg-background border-border rounded-xl text-sm text-foreground focus:ring-1 focus:ring-primary focus:border-primary placeholder:text-muted-foreground/50 py-3 pr-20 pl-12 resize-none overflow-y-hidden no-scrollbar" 
                />
                <div className="absolute right-2 bottom-1.5 flex items-center gap-1">
                    <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg text-muted-foreground hover:text-primary hover:bg-foreground/5" title="پیوست فایل">
                        <Paperclip className="h-4 w-4 -rotate-45" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg text-muted-foreground hover:text-primary hover:bg-foreground/5" title="ضبط صدا">
                        <Mic className="h-4 w-4" />
                    </Button>
                </div>
                <div className="absolute left-2 bottom-1.5 flex items-center">
                    <Button size="icon" className="h-9 w-9 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground transition-all shadow-lg shadow-primary/20 hover:scale-105 active:scale-95">
                        <Send className="h-4 w-4 rtl:-rotate-180" />
                    </Button>
                </div>
            </div>
        </div>
    </aside>
)};

const ChatMessage = ({ sender, time, message }) => {
    const isAI = sender === 'ai';
    return (
        <div className={`flex flex-col gap-1 ${!isAI && "items-end"}`}>
            <div className={`flex items-start gap-2 ${!isAI && "flex-row-reverse"}`}>
                {isAI && (
                    <div className="h-7 w-7 rounded-full bg-secondary flex-shrink-0 flex items-center justify-center border border-border mt-1">
                        <Bot className="text-primary h-4 w-4" />
                    </div>
                )}
                <div className={cn(
                    "p-3 rounded-2xl leading-6 shadow-sm border max-w-[90%]",
                    isAI ? "bg-card text-foreground rounded-tr-none border-border/50"
                         : "bg-primary/10 text-foreground rounded-tl-none border-primary/20"
                )}>
                    <p className="text-sm" dangerouslySetInnerHTML={{ __html: message }}></p>
                </div>
            </div>
        </div>
    );
};

export default function ExamPage() {
    const [isChatOpen, setIsChatOpen] = React.useState(true);

    const toggleChat = () => setIsChatOpen(!isChatOpen);

    return (
        <div className="bg-background font-body text-foreground antialiased min-h-screen flex flex-col overflow-hidden">
            <main className="flex-grow w-full max-w-[1920px] mx-auto p-0 h-screen flex flex-row overflow-hidden relative">
                
                <div className={cn("flex-1 flex flex-col relative transition-all duration-300 ease-in-out", isChatOpen ? "w-[calc(100%-24rem)]" : "w-full")}>
                    <ExamHeader />
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
                        <ChevronLeft className="h-6 w-6 mb-1 transition-transform group-hover:scale-110" />
                        <Bot className="h-6 w-6 transition-transform group-hover:scale-110" />
                    </button>
                )}
            </main>
        </div>
    );
}
