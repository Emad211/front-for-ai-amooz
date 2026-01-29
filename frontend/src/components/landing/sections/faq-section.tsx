'use client';

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { useLanding } from "@/hooks/use-landing";
import { motion } from 'framer-motion';
import { HelpCircle, MessageCircleQuestion } from 'lucide-react';

export const FAQSection = () => {
    const { faqs } = useLanding();

    return (
        <section id="faq" className="py-20 md:py-32 relative overflow-hidden">
            {/* Background */}
            <div className="absolute inset-0 bg-gradient-to-b from-muted/50 via-background to-muted/50" />
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_30%,rgba(var(--primary-rgb),0.08),transparent_50%)]" />
            
            <div className="container mx-auto px-4 relative z-10">
                {/* Section Header */}
                <motion.div 
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                    className="text-center max-w-3xl mx-auto mb-12 md:mb-16"
                >
                    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6">
                        <MessageCircleQuestion className="w-4 h-4 text-primary" />
                        <span className="text-sm font-medium text-primary">سوالات متداول</span>
                    </div>
                    <h2 className="text-3xl md:text-5xl lg:text-6xl font-black text-foreground mb-4">
                        پاسخ به{' '}
                        <span className="bg-gradient-to-l from-primary to-purple-500 bg-clip-text text-transparent">
                            سوالات
                        </span>
                        {' '}شما
                    </h2>
                    <p className="text-base md:text-xl text-muted-foreground">
                        اگر سوالی دارید، احتمالاً جوابش اینجاست
                    </p>
                </motion.div>
                
                {/* FAQ Accordion */}
                <motion.div 
                    initial={{ opacity: 0, y: 30 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6, delay: 0.2 }}
                    className="max-w-3xl mx-auto"
                >
                    <Accordion type="single" collapsible className="space-y-4">
                        {faqs.map((faq, index) => (
                            <motion.div
                                key={faq.id}
                                initial={{ opacity: 0, x: -20 }}
                                whileInView={{ opacity: 1, x: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.4, delay: index * 0.1 }}
                            >
                                <AccordionItem 
                                    value={faq.id} 
                                    className="group bg-gradient-to-br from-card/80 to-card/50 border border-border/50 rounded-2xl px-5 md:px-6 overflow-hidden hover:border-primary/30 transition-all duration-300 data-[state=open]:border-primary/40 data-[state=open]:shadow-lg data-[state=open]:shadow-primary/5"
                                >
                                    <AccordionTrigger className="text-base md:text-lg font-bold py-5 md:py-6 text-right hover:no-underline group-hover:text-primary transition-colors">
                                        <div className="flex items-center gap-3 w-full">
                                            <HelpCircle className="w-5 h-5 text-primary/60 group-data-[state=open]:text-primary transition-colors flex-shrink-0" />
                                            <span className="flex-1">{faq.question}</span>
                                        </div>
                                    </AccordionTrigger>
                                    <AccordionContent className="pb-5 md:pb-6 text-sm md:text-base text-muted-foreground leading-relaxed pr-8">
                                        {faq.answer}
                                    </AccordionContent>
                                </AccordionItem>
                            </motion.div>
                        ))}
                    </Accordion>
                </motion.div>
                
                {/* Contact CTA */}
                <motion.div 
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6, delay: 0.4 }}
                    className="text-center mt-12 md:mt-16"
                >
                    <p className="text-muted-foreground">
                        سوال دیگری دارید؟{' '}
                        <a href="#" className="text-primary hover:underline font-medium">با ما تماس بگیرید</a>
                    </p>
                </motion.div>
            </div>
        </section>
    );
};
