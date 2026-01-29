'use client';

import { Button } from '@/components/ui/button';
import { ArrowLeft, Sparkles, Rocket, Star } from 'lucide-react';
import Link from 'next/link';
import { useLanding } from '@/hooks/use-landing';
import { motion } from 'framer-motion';

export const FinalCTASection = () => {
    const { cta } = useLanding();

    return (
        <section className="py-20 md:py-32 relative overflow-hidden">
            {/* Animated Background */}
            <div className="absolute inset-0 bg-gradient-to-br from-primary/20 via-purple-500/10 to-primary/20" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(var(--primary-rgb),0.2),transparent_70%)]" />
            
            {/* Floating Elements */}
            <motion.div
                className="absolute top-10 left-[10%] text-primary/20"
                animate={{ y: [0, -20, 0], rotate: [0, 10, 0] }}
                transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
            >
                <Sparkles className="w-16 h-16" />
            </motion.div>
            <motion.div
                className="absolute bottom-20 right-[15%] text-yellow-500/20"
                animate={{ y: [0, 15, 0], rotate: [0, -15, 0] }}
                transition={{ duration: 7, repeat: Infinity, ease: "easeInOut", delay: 1 }}
            >
                <Star className="w-20 h-20" />
            </motion.div>
            <motion.div
                className="absolute top-1/2 left-[5%] text-purple-500/15"
                animate={{ x: [0, 20, 0] }}
                transition={{ duration: 8, repeat: Infinity, ease: "easeInOut", delay: 2 }}
            >
                <Rocket className="w-14 h-14" />
            </motion.div>
            
            <div className="container mx-auto px-4 relative z-10">
                <motion.div 
                    initial={{ opacity: 0, y: 30 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.7 }}
                    className="max-w-4xl mx-auto"
                >
                    {/* Card */}
                    <div className="relative rounded-3xl bg-gradient-to-br from-card/90 to-card/70 border border-white/10 backdrop-blur-xl p-8 md:p-16 text-center overflow-hidden">
                        {/* Inner Glow */}
                        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-96 h-96 bg-primary/20 rounded-full blur-[100px]" />
                        
                        <div className="relative z-10">
                            {/* Badge */}
                            <motion.div 
                                initial={{ scale: 0.9 }}
                                whileInView={{ scale: 1 }}
                                viewport={{ once: true }}
                                className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/20 border border-primary/30 mb-6"
                            >
                                <motion.div
                                    animate={{ rotate: 360 }}
                                    transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
                                >
                                    <Rocket className="w-4 h-4 text-primary" />
                                </motion.div>
                                <span className="text-sm font-medium text-primary">همین حالا شروع کن</span>
                            </motion.div>
                            
                            <h2 className="text-3xl md:text-5xl lg:text-6xl font-black text-foreground mb-4 md:mb-6 leading-tight">
                                {cta.title}
                            </h2>
                            <p className="text-base md:text-xl text-muted-foreground mb-8 md:mb-10 max-w-2xl mx-auto leading-relaxed">
                                {cta.description}
                            </p>
                            
                            <motion.div
                                whileHover={{ scale: 1.05 }}
                                whileTap={{ scale: 0.98 }}
                            >
                                <Button 
                                    asChild 
                                    size="lg" 
                                    className="group h-14 md:h-16 px-12 text-lg md:text-xl bg-gradient-to-r from-primary to-purple-600 text-primary-foreground hover:from-primary/90 hover:to-purple-600/90 shadow-2xl shadow-primary/30 transition-all"
                                >
                                    <Link href="/login">
                                        <span className="flex items-center">
                                            {cta.button}
                                            <ArrowLeft className="mr-2 h-5 w-5 transition-transform group-hover:-translate-x-1" />
                                        </span>
                                    </Link>
                                </Button>
                            </motion.div>
                            
                            <p className="text-sm text-muted-foreground mt-6 flex items-center justify-center gap-2">
                                <Sparkles className="w-4 h-4 text-primary" />
                                {cta.footer}
                            </p>
                        </div>
                    </div>
                </motion.div>
            </div>
        </section>
    );
};
