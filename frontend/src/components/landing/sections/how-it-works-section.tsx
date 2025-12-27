'use client';

import { Play } from 'lucide-react';

// Step Card for Mobile - Completely different design
const StepCardMobile = ({ number, title, description, isLast }: { number: string, title: string, description: string, isLast?: boolean }) => (
    <div className="relative">
        <div className="flex gap-4">
            {/* Number Circle with connecting line */}
            <div className="flex flex-col items-center">
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-primary to-primary/70 text-primary-foreground flex items-center justify-center text-xl font-bold shadow-lg shadow-primary/30 z-10">
                    {number}
                </div>
                {!isLast && (
                    <div className="w-0.5 h-full bg-gradient-to-b from-primary to-primary/20 mt-2"></div>
                )}
            </div>
            
            {/* Content */}
            <div className="flex-1 pb-8">
                <div className="bg-gradient-to-br from-card to-card/50 rounded-2xl p-5 border border-border/50 shadow-lg">
                    <h3 className="text-lg font-bold text-foreground mb-2">{title}</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
                </div>
            </div>
        </div>
    </div>
);

const StepItem = ({ number, title, description, align }: { number: string, title: string, description: string, align: 'right' | 'left' }) => (
    <div className={`relative flex items-center gap-6 md:gap-8 ${align === 'left' ? 'md:flex-row-reverse' : ''}`}>
        <div className={`flex-1 ${align === 'left' ? 'md:text-left' : 'md:text-right'} text-right pr-14 md:pr-0`}>
            <div className="p-5 md:p-6 rounded-2xl bg-card/50 border border-border/50 inline-block transition-transform hover:scale-[1.02] duration-300">
                <h3 className="text-lg md:text-xl font-bold text-foreground mb-1 md:mb-2">{title}</h3>
                <p className="text-sm md:text-base text-muted-foreground">{description}</p>
            </div>
        </div>
        <div className="absolute right-0 md:right-1/2 md:translate-x-1/2 w-10 h-10 md:w-12 md:h-12 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-lg md:text-xl font-bold shadow-lg shadow-primary/30 z-10">
            {number}
        </div>
        <div className="flex-1 hidden md:block"></div>
    </div>
);

export const HowItWorksSection = () => (
    <section id="how-it-works" className="py-20 md:py-32 relative bg-muted/80 dark:bg-card/80">

        <div className="container mx-auto px-4 relative z-10">
            <div className="text-center max-w-2xl mx-auto mb-12 md:mb-20">
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6">
                    <Play className="w-4 h-4 text-primary" />
                    <span className="text-sm font-medium text-primary">نحوه کار</span>
                </div>
                <h2 className="text-2xl md:text-5xl font-bold text-foreground">
                    شروع در ۳ مرحله ساده
                </h2>
            </div>
            
            {/* Desktop Layout */}
            <div className="hidden md:block max-w-4xl mx-auto">
                <div className="relative">
                    {/* Connection Line */}
                    <div className="absolute top-0 bottom-0 right-1/2 w-px bg-gradient-to-b from-primary via-primary/50 to-primary/20 z-0"></div>
                    
                    <div className="space-y-24">
                        <StepItem 
                            number="۱"
                            title="ثبت‌نام و تعیین هدف"
                            description="به ما بگویید در چه درسی و برای چه هدفی به کمک نیاز دارید. کنکور، امتحان نهایی یا تقویت پایه."
                            align="right"
                        />
                        <StepItem 
                            number="۲"
                            title="دریافت نقشه راه"
                            description="هوش مصنوعی یک مسیر یادگیری مخصوص شما شامل درسنامه، تمرین و آزمون ایجاد می‌کند."
                            align="left"
                        />
                        <StepItem 
                            number="۳"
                            title="شروع یادگیری"
                            description="با همراهی دستیار هوشمند مراحل را طی کنید و پیشرفت خود را لحظه به لحظه ببینید."
                            align="right"
                        />
                    </div>
                </div>
            </div>

            {/* Mobile Layout - Vertical Timeline */}
            <div className="md:hidden max-w-md mx-auto">
                <StepCardMobile 
                    number="۱"
                    title="ثبت‌نام و تعیین هدف"
                    description="به ما بگویید در چه درسی و برای چه هدفی به کمک نیاز دارید."
                />
                <StepCardMobile 
                    number="۲"
                    title="دریافت نقشه راه"
                    description="هوش مصنوعی یک مسیر یادگیری مخصوص شما ایجاد می‌کند."
                />
                <StepCardMobile 
                    number="۳"
                    title="شروع یادگیری"
                    description="با همراهی دستیار هوشمند پیشرفت خود را ببینید."
                    isLast
                />
            </div>
        </div>
    </section>
);
