'use client';

import { Sparkles, Target, Zap, Brain, Bot, BookCheck, BarChart3 } from 'lucide-react';
import { useLanding } from '@/hooks/use-landing';

const IconMap = {
    Target: <Target className="h-8 w-8" />,
    Zap: <Zap className="h-8 w-8" />,
    Brain: <Brain className="h-8 w-8" />,
    Bot: <Bot className="h-8 w-8" />,
    BookCheck: <BookCheck className="h-8 w-8" />,
    BarChart3: <BarChart3 className="h-8 w-8" />
};

const MobileIconMap = {
    Target: <Target className="h-6 w-6" />,
    Zap: <Zap className="h-6 w-6" />,
    Brain: <Brain className="h-6 w-6" />,
    Bot: <Bot className="h-6 w-6" />,
    BookCheck: <BookCheck className="h-6 w-6" />,
    BarChart3: <BarChart3 className="h-6 w-6" />
};

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

export const FeaturesSection = () => {
    const { features } = useLanding();

    return (
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
                    {features.filter(f => f.id <= 4).map((feature) => (
                        <FeatureCardLarge 
                            key={feature.id}
                            icon={IconMap[feature.icon as keyof typeof IconMap]}
                            title={feature.title}
                            description={feature.description}
                            className={feature.large ? "col-span-2 row-span-1" : "col-span-1 row-span-1"}
                        />
                    ))}
                </div>

                {/* Mobile: Horizontal Cards */}
                <div className="md:hidden space-y-4">
                    {features.map((feature, index) => (
                        <FeatureCardMobile 
                            key={feature.id}
                            icon={MobileIconMap[feature.icon as keyof typeof MobileIconMap]}
                            title={feature.title}
                            description={feature.description}
                            index={index}
                        />
                    ))}
                </div>
            </div>
        </section>
    );
};
);
