'use client';

import { Sparkles, Target, Zap, Brain, Bot, BookCheck, BarChart3, GraduationCap, MessageCircle, FileText } from 'lucide-react';
import { useLanding } from '@/hooks/use-landing';
import { motion } from 'framer-motion';

const IconMap = {
    Target: Target,
    Zap: Zap,
    Brain: Brain,
    Bot: Bot,
    BookCheck: BookCheck,
    BarChart3: BarChart3,
    GraduationCap: GraduationCap,
    MessageCircle: MessageCircle,
    FileText: FileText,
};

// Bento Grid Feature Card - Premium Design
const FeatureCard = ({ 
    icon, 
    title, 
    description, 
    index,
    gradient,
    iconColor,
}: { 
    icon: React.ReactNode; 
    title: string; 
    description: string;
    index: number;
    gradient: string;
    iconColor: string;
}) => (
    <motion.div 
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-50px" }}
        transition={{ duration: 0.5, delay: index * 0.1 }}
        className="group relative"
    >
        <div className={`relative h-full overflow-hidden rounded-3xl bg-gradient-to-br ${gradient} border border-white/10 p-6 md:p-8 transition-all duration-500 hover:scale-[1.02] hover:shadow-2xl`}>
            {/* Animated glow */}
            <div className="absolute -top-20 -right-20 w-40 h-40 bg-white/10 rounded-full blur-3xl opacity-0 group-hover:opacity-100 transition-all duration-700" />
            
            {/* Icon Container */}
            <motion.div 
                className={`w-14 h-14 md:w-16 md:h-16 rounded-2xl bg-white/10 backdrop-blur-sm flex items-center justify-center ${iconColor} mb-5 group-hover:scale-110 transition-transform duration-300`}
                whileHover={{ rotate: [0, -10, 10, 0] }}
                transition={{ duration: 0.5 }}
            >
                {icon}
            </motion.div>
            
            {/* Content */}
            <h3 className="text-xl md:text-2xl font-bold text-white mb-3">{title}</h3>
            <p className="text-white/70 leading-relaxed text-sm md:text-base">{description}</p>
            
            {/* Decorative corner */}
            <div className="absolute bottom-0 left-0 w-20 h-20 bg-gradient-to-tr from-white/5 to-transparent rounded-tr-full" />
        </div>
    </motion.div>
);

// Mobile Feature Card
const FeatureCardMobile = ({ 
    icon, 
    title, 
    description, 
    index,
    gradient,
}: { 
    icon: React.ReactNode; 
    title: string; 
    description: string; 
    index: number;
    gradient: string;
}) => (
    <motion.div 
        initial={{ opacity: 0, x: -20 }}
        whileInView={{ opacity: 1, x: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4, delay: index * 0.1 }}
        className={`flex gap-4 p-5 rounded-2xl bg-gradient-to-l ${gradient} border border-white/10`}
    >
        <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center text-white shadow-lg">
            {icon}
        </div>
        <div>
            <h3 className="text-lg font-bold text-white mb-1">{title}</h3>
            <p className="text-sm text-white/70 leading-relaxed">{description}</p>
        </div>
    </motion.div>
);

const featureStyles = [
    { gradient: 'from-violet-600/90 to-purple-700/90', iconColor: 'text-violet-200' },
    { gradient: 'from-cyan-600/90 to-blue-700/90', iconColor: 'text-cyan-200' },
    { gradient: 'from-amber-500/90 to-orange-600/90', iconColor: 'text-amber-200' },
    { gradient: 'from-emerald-600/90 to-teal-700/90', iconColor: 'text-emerald-200' },
    { gradient: 'from-rose-600/90 to-pink-700/90', iconColor: 'text-rose-200' },
    { gradient: 'from-indigo-600/90 to-blue-700/90', iconColor: 'text-indigo-200' },
];

export const FeaturesSection = () => {
    const { features } = useLanding();

    return (
        <section id="features" className="py-20 md:py-32 relative overflow-hidden">
            {/* Background */}
            <div className="absolute inset-0 bg-gradient-to-b from-background via-primary/5 to-background" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(var(--primary-rgb),0.15),transparent_50%)]" />
            
            <div className="container mx-auto px-4 relative z-10">
                {/* Section Header */}
                <motion.div 
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                    className="text-center max-w-3xl mx-auto mb-12 md:mb-20"
                >
                    <motion.div 
                        initial={{ scale: 0.9, opacity: 0 }}
                        whileInView={{ scale: 1, opacity: 1 }}
                        viewport={{ once: true }}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6"
                    >
                        <Sparkles className="w-4 h-4 text-primary" />
                        <span className="text-sm font-medium text-primary">ویژگی‌های منحصربه‌فرد</span>
                    </motion.div>
                    
                    <h2 className="text-3xl md:text-5xl lg:text-6xl font-black text-foreground mb-4 md:mb-6">
                        چرا{' '}
                        <span className="bg-gradient-to-l from-primary via-purple-500 to-primary bg-clip-text text-transparent">
                          همسفر ما
                        </span>
                        {' '}شوید؟
                    </h2>
                    <p className="text-base md:text-xl text-muted-foreground leading-relaxed">
                        ابزارهای هوشمندی که یادگیری را برای شما شخصی‌سازی می‌کنند و مسیر پیشرفتتان را هموار می‌سازند
                    </p>
                </motion.div>
                
                {/* Desktop: Bento Grid */}
                <div className="hidden md:grid grid-cols-3 gap-5 max-w-6xl mx-auto">
                    {features.slice(0, 6).map((feature, index) => {
                        const IconComponent = IconMap[feature.icon as keyof typeof IconMap] || Target;
                        const style = featureStyles[index % featureStyles.length];
                        return (
                            <FeatureCard 
                                key={feature.id}
                                icon={<IconComponent className="h-7 w-7" />}
                                title={feature.title}
                                description={feature.description}
                                index={index}
                                gradient={style.gradient}
                                iconColor={style.iconColor}
                            />
                        );
                    })}
                </div>

                {/* Mobile: Stacked Cards */}
                <div className="md:hidden space-y-4">
                    {features.map((feature, index) => {
                        const IconComponent = IconMap[feature.icon as keyof typeof IconMap] || Target;
                        const style = featureStyles[index % featureStyles.length];
                        return (
                            <FeatureCardMobile 
                                key={feature.id}
                                icon={<IconComponent className="h-5 w-5" />}
                                title={feature.title}
                                description={feature.description}
                                index={index}
                                gradient={style.gradient}
                            />
                        );
                    })}
                </div>
            </div>
        </section>
    );
};
