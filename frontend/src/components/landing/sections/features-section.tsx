'use client';

import { Sparkles, Target, Zap, Brain, Bot, BookCheck, BarChart3 } from 'lucide-react';

// Feature Card for Desktop - Bento Grid Style
const FeatureCardLarge = ({ icon, title, description, className = "" }: { icon: React.ReactNode, title: string, description: string, className?: string }) => (
    <div className={`group relative overflow-hidden rounded-3xl bg-gradient-to-br from-card/80 to-card/40 border border-border/50 backdrop-blur-sm p-8 transition-all duration-500 hover:border-primary/40 hover:shadow-2xl hover:shadow-primary/10 ${className}`}>
        {/* Animated background glow */}
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-primary/20 rounded-full blur-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-700"></div>
        <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-primary/10 rounded-full blur-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-700" style={{ transitionDelay: '200ms' }}></div>
        
        <div className="relative z-10">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center text-primary mb-6 group-hover:scale-110 transition-transform duration-300">
                {icon}
            </div>
            <h3 className="text-2xl font-bold text-foreground mb-3">{title}</h3>
            <p className="text-muted-foreground leading-relaxed">{description}</p>
        </div>
    </div>
);

// Feature Card for Mobile - Horizontal Style
const FeatureCardMobile = ({ icon, title, description, index }: { icon: React.ReactNode, title: string, description: string, index: number }) => (
    <div 
        className="flex gap-4 p-5 rounded-2xl bg-gradient-to-l from-primary/5 to-transparent border-r-4 border-primary/60 hover:from-primary/10 transition-all duration-300"
        style={{ animationDelay: `${index * 150}ms` }}
    >
        <div className="flex-shrink-0 w-14 h-14 rounded-xl bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center text-primary-foreground shadow-lg shadow-primary/30">
            {icon}
        </div>
        <div>
            <h3 className="text-lg font-bold text-foreground mb-1">{title}</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
        </div>
    </div>
);

export const FeaturesSection = () => (
    <section id="features" className="py-20 md:py-32 relative bg-primary/10 dark:bg-primary/5">
        
        <div className="container mx-auto px-4 relative z-10">
            <div className="text-center max-w-2xl mx-auto mb-12 md:mb-20">
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6">
                    <Sparkles className="w-4 h-4 text-primary" />
                    <span className="text-sm font-medium text-primary">ویژگی‌ها</span>
                </div>
                <h2 className="text-2xl md:text-5xl font-bold text-foreground">
                    چرا AI-Amooz متفاوت است؟
                </h2>
                <p className="text-sm md:text-lg text-muted-foreground mt-4 md:mt-6">
                    ابزارهای هوشمندی که یادگیری را برای شما شخصی‌سازی می‌کنند
                </p>
            </div>
            
            {/* Desktop: Bento Grid */}
            <div className="hidden md:grid grid-cols-3 gap-6 max-w-6xl mx-auto">
                <FeatureCardLarge 
                    icon={<Target className="h-8 w-8" />}
                    title="مسیر یادگیری شخصی"
                    description="هوش مصنوعی سطح دانش شما را می‌سنجد و بهترین مسیر آموزشی را برای رسیدن به اهداف‌تان طراحی می‌کند."
                    className="col-span-2 row-span-1"
                />
                <FeatureCardLarge 
                    icon={<Zap className="h-8 w-8" />}
                    title="یادگیری سریع"
                    description="با متدهای هوشمند، سریع‌تر یاد بگیرید."
                    className="col-span-1 row-span-1"
                />
                <FeatureCardLarge 
                    icon={<Brain className="h-8 w-8" />}
                    title="تحلیل پیشرفت"
                    description="نقاط ضعف و قوت خود را بشناسید."
                    className="col-span-1 row-span-1"
                />
                <FeatureCardLarge 
                    icon={<Bot className="h-8 w-8" />}
                    title="دستیار هوشمند ۲۴/۷"
                    description="در هر لحظه سوالات درسی بپرسید، راه‌حل‌های مختلف را بررسی کنید و اشکالات خود را رفع کنید."
                    className="col-span-2 row-span-1"
                />
            </div>

            {/* Mobile: Horizontal Cards */}
            <div className="md:hidden space-y-4">
                <FeatureCardMobile 
                    icon={<Target className="h-6 w-6" />}
                    title="مسیر یادگیری شخصی"
                    description="هوش مصنوعی بهترین مسیر آموزشی را برای شما طراحی می‌کند."
                    index={0}
                />
                <FeatureCardMobile 
                    icon={<Bot className="h-6 w-6" />}
                    title="دستیار هوشمند ۲۴/۷"
                    description="در هر لحظه سوالات درسی بپرسید و اشکالات خود را رفع کنید."
                    index={1}
                />
                <FeatureCardMobile 
                    icon={<BookCheck className="h-6 w-6" />}
                    title="آزمون‌های تطبیقی"
                    description="آزمون‌هایی که بر اساس نقاط ضعف و قوت شما طراحی می‌شوند."
                    index={2}
                />
                <FeatureCardMobile 
                    icon={<BarChart3 className="h-6 w-6" />}
                    title="تحلیل پیشرفت"
                    description="نقاط ضعف و قوت خود را بشناسید و بهبود دهید."
                    index={3}
                />
            </div>
        </div>
    </section>
);
