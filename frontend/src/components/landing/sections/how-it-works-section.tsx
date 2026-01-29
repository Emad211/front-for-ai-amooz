'use client';

import { Play, Upload, BookOpen, Rocket, CheckCircle2 } from 'lucide-react';
import { useLanding } from '@/hooks/use-landing';
import { motion } from 'framer-motion';

const stepIcons = [Upload, BookOpen, Rocket];

export const HowItWorksSection = () => {
    const { steps } = useLanding();

    return (
        <section id="how-it-works" className="py-20 md:py-32 relative overflow-hidden">
            {/* Background */}
            <div className="absolute inset-0 bg-gradient-to-b from-muted/50 via-background to-muted/50" />
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_50%,rgba(var(--primary-rgb),0.08),transparent_50%)]" />
            
            <div className="container mx-auto px-4 relative z-10">
                {/* Section Header */}
                <motion.div 
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                    className="text-center max-w-3xl mx-auto mb-16 md:mb-24"
                >
                    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6">
                        <Play className="w-4 h-4 text-primary" />
                        <span className="text-sm font-medium text-primary">شروع آسان</span>
                    </div>
                    <h2 className="text-3xl md:text-5xl lg:text-6xl font-black text-foreground mb-4">
                        در{' '}
                        <span className="bg-gradient-to-l from-primary to-purple-500 bg-clip-text text-transparent">
                            سه قدم ساده
                        </span>
                        {' '}شروع کنید
                    </h2>
                    <p className="text-base md:text-xl text-muted-foreground">
                        فقط چند دقیقه وقت بگذارید و سفر یادگیری‌تان را آغاز کنید
                    </p>
                </motion.div>
                
                {/* Desktop Layout - Horizontal Steps */}
                <div className="hidden md:block max-w-5xl mx-auto">
                    <div className="relative">
                        {/* Connection Line */}
                        <div className="absolute top-24 left-[15%] right-[15%] h-1 bg-gradient-to-r from-primary/20 via-primary to-primary/20 rounded-full" />
                        
                        <div className="grid grid-cols-3 gap-8">
                            {steps.map((step, index) => {
                                const IconComponent = stepIcons[index] || CheckCircle2;
                                return (
                                    <motion.div
                                        key={step.id}
                                        initial={{ opacity: 0, y: 40 }}
                                        whileInView={{ opacity: 1, y: 0 }}
                                        viewport={{ once: true }}
                                        transition={{ duration: 0.6, delay: index * 0.2 }}
                                        className="relative"
                                    >
                                        {/* Step Number Circle */}
                                        <div className="relative z-10 flex justify-center mb-8">
                                            <motion.div 
                                                className="relative"
                                                whileHover={{ scale: 1.1 }}
                                                transition={{ type: "spring", stiffness: 300 }}
                                            >
                                                {/* Glow */}
                                                <div className="absolute inset-0 bg-primary rounded-full blur-xl opacity-40" />
                                                
                                                {/* Circle */}
                                                <div className="relative w-20 h-20 rounded-full bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center shadow-2xl shadow-primary/30">
                                                    <span className="text-3xl font-black text-white">{step.number}</span>
                                                </div>
                                                
                                                {/* Icon Badge */}
                                                <div className="absolute -bottom-2 -right-2 w-10 h-10 rounded-full bg-background border-2 border-primary flex items-center justify-center">
                                                    <IconComponent className="w-5 h-5 text-primary" />
                                                </div>
                                            </motion.div>
                                        </div>
                                        
                                        {/* Content Card */}
                                        <motion.div 
                                            className="text-center p-6 rounded-2xl bg-card/50 border border-border/50 backdrop-blur-sm hover:border-primary/30 hover:bg-card/80 transition-all duration-300"
                                            whileHover={{ y: -5 }}
                                        >
                                            <h3 className="text-xl font-bold text-foreground mb-3">{step.title}</h3>
                                            <p className="text-muted-foreground leading-relaxed">{step.description}</p>
                                        </motion.div>
                                    </motion.div>
                                );
                            })}
                        </div>
                    </div>
                </div>

                {/* Mobile Layout - Vertical Timeline */}
                <div className="md:hidden max-w-md mx-auto">
                    {steps.map((step, index) => {
                        const IconComponent = stepIcons[index] || CheckCircle2;
                        const isLast = index === steps.length - 1;
                        
                        return (
                            <motion.div 
                                key={step.id}
                                initial={{ opacity: 0, x: -20 }}
                                whileInView={{ opacity: 1, x: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.5, delay: index * 0.15 }}
                                className="relative flex gap-5"
                            >
                                {/* Timeline */}
                                <div className="flex flex-col items-center">
                                    {/* Number Circle */}
                                    <div className="relative">
                                        <div className="absolute inset-0 bg-primary rounded-full blur-lg opacity-30" />
                                        <div className="relative w-14 h-14 rounded-full bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center shadow-xl shadow-primary/30 z-10">
                                            <span className="text-xl font-bold text-white">{step.number}</span>
                                        </div>
                                    </div>
                                    
                                    {/* Connecting Line */}
                                    {!isLast && (
                                        <div className="w-0.5 flex-1 bg-gradient-to-b from-primary to-primary/20 my-2" />
                                    )}
                                </div>
                                
                                {/* Content */}
                                <div className="flex-1 pb-10">
                                    <div className="bg-card/50 rounded-2xl p-5 border border-border/50 backdrop-blur-sm">
                                        <div className="flex items-center gap-3 mb-2">
                                            <IconComponent className="w-5 h-5 text-primary" />
                                            <h3 className="text-lg font-bold text-foreground">{step.title}</h3>
                                        </div>
                                        <p className="text-sm text-muted-foreground leading-relaxed">{step.mobileDescription}</p>
                                    </div>
                                </div>
                            </motion.div>
                        );
                    })}
                </div>
            </div>
        </section>
    );
};
