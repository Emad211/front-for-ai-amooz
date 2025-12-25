'use client';

import React from 'react';
import Link from 'next/link';
import { Header } from '@/components/layout/header';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Textarea } from '@/components/ui/textarea';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { 
    ArrowLeft, 
    List, 
    Flag, 
    Hourglass, 
    FolderOpen, 
    ChevronDown, 
    Book, 
    PlayCircle, 
    FileText, 
    CheckCircle,
    ChevronUp,
    Folder,
    Lock,
    BookOpen,
    Settings,
    RotateCcw,
    Lightbulb,
    Check,
    Bot,
    MoreVertical,
    Paperclip,
    Mic,
    Send,
    Signal,
    Clock,
    BarChart,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import '../learn.css';


const CourseSidebar = () => (
    <aside className="w-80 flex-shrink-0 flex-col gap-3 hidden lg:flex h-full">
        <Button variant="outline" asChild className="bg-card hover:bg-card/80 border-border text-muted-foreground hover:text-foreground rounded-xl p-3 flex items-center justify-between transition-all group h-12">
            <Link href="/classes">
                <span className="text-sm font-medium pr-1">بازگشت به لیست دوره‌ها</span>
                <ArrowLeft className="text-muted-foreground group-hover:text-foreground group-hover:-translate-x-1 transition-all h-5 w-5" />
            </Link>
        </Button>
        <div className="flex-1 bg-card border border-border rounded-2xl flex flex-col overflow-hidden shadow-lg">
            <div className="p-4 border-b border-border/50 flex items-center justify-between">
                <h3 className="font-bold text-foreground text-sm flex items-center gap-2">
                    <List className="text-primary h-5 w-5" />
                    فهرست مطالب
                </h3>
                <span className="text-[10px] text-muted-foreground bg-secondary px-2 py-0.5 rounded-full">8 بخش</span>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1 no-scrollbar">
                <SidebarItem icon={<Flag className="h-5 w-5" />} title="اهداف یادگیری" />
                <SidebarItem icon={<Hourglass className="h-5 w-5" />} title="پیش نیازها" />
                
                <div>
                    <div className="flex items-center justify-between p-3 rounded-xl bg-primary/10 text-foreground cursor-pointer">
                        <div className="flex items-center gap-3">
                            <FolderOpen className="text-primary h-5 w-5" />
                            <span className="text-sm font-bold">آشنایی با سهمی</span>
                        </div>
                        <ChevronUp className="h-4 w-4" />
                    </div>
                    <div className="p-1 space-y-1">
                       <SubmenuItem icon={<FileText className="h-4 w-4" />} title="شکل کلی و جهت سهمی" />
                       <SubmenuItem icon={<PlayCircle className="h-4 w-4" />} title="رأس سهمی: مهمترین نقطه" active />
                       <SubmenuItem icon={<FileText className="h-4 w-4" />} title="ارتباط رأس با نقاط متقارن" />
                       <SubmenuItem icon={<Book className="h-4 w-4" />} title="عرض از مبدأ و ریشه‌ها" />
                       <SubmenuItem icon={<CheckCircle className="h-4 w-4 text-green-400" />} title="آزمون فصل" special />
                    </div>
                </div>

                <SidebarItem icon={<Folder className="h-5 w-5" />} title="گام به گام رسم نمودار" expandable />
                <SidebarItem icon={<Folder className="h-5 w-5" />} title="حل مسائل مربوطه" expandable />
                <SidebarItem icon={<Lock className="h-5 w-5" />} title="آزمون نهایی دوره" disabled />
                <SidebarItem icon={<BookOpen className="h-5 w-5" />} title="خلاصه و نکات" />
            </div>
            <div className="p-3 border-t border-border/50 space-y-2 bg-background/20">
                <Button variant="outline" className="w-full justify-between p-2.5 h-auto bg-secondary/50 border-border text-primary hover:bg-primary/10 hover:border-primary/30 transition-all">
                    <span className="text-xs font-bold">دانلود جزوه</span>
                    <BookOpen className="h-4 w-4" />
                </Button>
                <div className="flex gap-2">
                    <Button variant="outline" className="flex-1 justify-center gap-2 p-2.5 h-auto bg-secondary/50 border-border text-muted-foreground hover:text-foreground hover:bg-secondary">
                        <span className="text-xs font-medium">تنظیمات</span>
                        <Settings className="h-4 w-4" />
                    </Button>
                     <Button variant="outline" className="flex-1 justify-center gap-2 p-2.5 h-auto bg-secondary/50 border-border text-muted-foreground hover:text-foreground hover:bg-secondary">
                        <span className="text-xs font-medium">شروع مجدد</span>
                        <RotateCcw className="h-4 w-4" />
                    </Button>
                </div>
            </div>
        </div>
    </aside>
);

const SidebarItem = ({ icon, title, disabled = false, expandable = false }) => (
    <div className={cn("group", disabled && "cursor-not-allowed text-muted-foreground/40")}>
        <div className={cn("flex items-center justify-between p-3 rounded-xl cursor-pointer transition-all", 
            disabled ? "" : "text-muted-foreground hover:bg-secondary/30 hover:text-foreground border border-transparent hover:border-border/30"
        )}>
            <div className="flex items-center gap-3">
                {React.cloneElement(icon, { className: cn("h-5 w-5", disabled ? "text-muted-foreground/40" : "text-muted-foreground") })}
                <span className="text-sm font-medium">{title}</span>
            </div>
            {expandable && <ChevronDown className="h-4 w-4 text-muted-foreground/60" />}
        </div>
    </div>
);


const SubmenuItem = ({ icon, title, active = false, special = false }) => (
    <div className={cn(
        "flex items-center gap-3 p-2 pr-4 rounded-lg cursor-pointer",
        active ? "bg-primary/10 text-primary border border-primary/20" : "text-muted-foreground hover:text-foreground hover:bg-foreground/5",
        special && "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 mt-1"
    )}>
        {React.cloneElement(icon, { className: cn("h-4 w-4", !active && "text-muted-foreground") })}
        <span className={cn("text-xs", (active || special) && "font-bold")}>{title}</span>
    </div>
);


const LessonContent = () => (
    <section className="flex-1 flex flex-col gap-3 overflow-y-auto no-scrollbar h-full rounded-2xl relative">
        <div className="bg-card border border-border rounded-2xl p-4 shadow-lg relative overflow-hidden flex-shrink-0">
             <div className="flex flex-col gap-4">
                <div>
                    <h1 className="text-base font-bold text-foreground mb-1">
                        رسم نمودار توابع درجه دوم (سهمی)
                    </h1>
                    <p className="text-muted-foreground text-xs leading-relaxed line-clamp-1">
                        یادگیری چگونگی رسم دقیق نمودارهای توابع درجه دوم (سهمی) و تفسیر ویژگی‌های کلیدی آن‌ها.
                    </p>
                </div>
                 <div className="flex items-center justify-between text-xs text-muted-foreground border-t border-border pt-3">
                    <div className="flex items-center gap-2">
                        <BarChart className="h-4 w-4 text-primary"/>
                        <span>تکمیل: <span className="font-bold text-foreground">۶۷٪</span></span>
                    </div>
                    <div className="flex items-center gap-2">
                        <Signal className="h-4 w-4 text-primary"/>
                        <span>سطح: <span className="font-bold text-foreground">مبتدی</span></span>
                    </div>
                    <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4 text-primary"/>
                        <span>زمان: <span className="font-bold text-foreground">۳۰-۴۵ دقیقه</span></span>
                    </div>
                </div>
            </div>
        </div>
        <div className="bg-card border border-border rounded-2xl p-6 sm:p-8 flex-1 shadow-xl overflow-y-auto no-scrollbar">
            <div className="flex items-center gap-3 mb-6 pb-3 border-b border-border/50">
                <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                    <PlayCircle className="h-5 w-5" />
                </div>
                <h2 className="text-lg font-bold text-foreground">رأس سهمی: مهمترین نقطه</h2>
            </div>
            <div className="space-y-4 max-w-4xl mx-auto">
               <p className="text-muted-foreground leading-7 text-justify">
                   اینجا محتوای درس در مورد "رأس سهمی" نمایش داده می‌شود. شما می‌توانید متن، تصویر، ویدیو و سایر موارد آموزشی را در این قسمت قرار دهید. طبق درخواست شما، این بخش به صورت یک متن ساده پیاده‌سازی شده است.
               </p>
            </div>
        </div>
    </section>
);

const ChatAssistant = () => (
     <aside className="w-96 flex-shrink-0 flex-col bg-card border border-border rounded-2xl overflow-hidden shadow-xl h-full hidden md:flex">
        <div className="p-3 border-b border-border flex items-center justify-between bg-secondary/30 backdrop-blur-sm h-14">
            <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-primary/20 to-purple-500/20 flex items-center justify-center relative ring-1 ring-foreground/10">
                    <Bot className="text-primary h-5 w-5" />
                    <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 bg-green-500 rounded-full border-2 border-card"></span>
                </div>
                <div>
                    <h3 className="text-sm font-bold text-foreground">دستیار هوشمند</h3>
                    <p className="text-[10px] text-muted-foreground font-medium">پاسخگوی سوالات شما</p>
                </div>
            </div>
            <Button variant="ghost" size="icon" className="h-7 w-7 rounded text-muted-foreground hover:text-foreground">
                <MoreVertical className="h-4 w-4" />
            </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-6 bg-background/30 no-scrollbar">
            <ChatMessage sender="ai" time="۱۰:۳۲" message="سلام علی! 👋 <br/>من آماده‌ام تا در مورد «رأس سهمی» بهت کمک کنم. سوالی داری؟" />
            <ChatMessage sender="user" time="۱۰:۳۴" message="فرمول x رأس سهمی چی بود؟" />
            <ChatMessage sender="ai" time="۱۰:۳۴" isFormula message='فرمول محاسبه طول رأس سهمی برابر است با: <br/> <span class="font-mono text-purple-400 bg-black/20 px-1 rounded my-1 block text-center" dir="ltr">x = -b / 2a</span>' />
        </div>
        <div className="p-3 border-t border-border bg-card z-10">
            <div className="relative">
                <Textarea placeholder="سوالت رو بنویس..." className="bg-background border-border rounded-xl text-xs text-foreground focus:ring-1 focus:ring-primary focus:border-primary placeholder:text-muted-foreground/50 min-h-[48px] max-h-24 py-3 pr-20 pl-12 resize-none no-scrollbar" />
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
);

const ChatMessage = ({ sender, time, message, isFormula=false }) => {
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
                    "text-sm p-3 rounded-2xl leading-6 shadow-sm border max-w-[90%]",
                    isAI ? "bg-card text-gray-200 rounded-tr-none border-border/50"
                         : "bg-primary/10 text-foreground rounded-tl-none border-primary/20"
                )}>
                    <p className="text-xs" dangerouslySetInnerHTML={{ __html: message }}></p>
                </div>
            </div>
            <span className={`text-[9px] text-muted-foreground ${isAI ? 'pr-11' : 'pl-1'}`}>{time}</span>
        </div>
    );
};

export default function LearnPage() {
    return (
        <div className="bg-background font-body text-foreground antialiased min-h-screen flex flex-col overflow-hidden">
            <Header />
            <main className="flex-grow w-full max-w-[1920px] mx-auto p-4 h-[calc(100vh-64px)] flex gap-4 overflow-hidden">
                <CourseSidebar />
                <LessonContent />
                <ChatAssistant />
            </main>
        </div>
    );
}
