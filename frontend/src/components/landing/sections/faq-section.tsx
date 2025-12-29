'use client';

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { useLanding } from "@/hooks/use-landing";

export const FAQSection = () => {
    const { faqs } = useLanding();

    return (
        <section id="faq" className="py-20 md:py-32 bg-muted/80 dark:bg-card/80">
            <div className="container mx-auto px-4">
                <div className="text-center max-w-2xl mx-auto mb-12 md:mb-16">
                    <span className="text-primary font-semibold text-xs md:text-sm tracking-wider uppercase">سوالات متداول</span>
                    <h2 className="text-2xl md:text-5xl font-bold text-foreground mt-3 md:mt-4">
                        پاسخ به سوالات شما
                    </h2>
                </div>
                
                <div className="max-w-3xl mx-auto">
                    <Accordion type="single" collapsible className="space-y-3 md:space-y-4">
                        {faqs.map((faq) => (
                            <AccordionItem key={faq.id} value={faq.id} className="bg-card/50 border border-border/50 rounded-xl md:rounded-2xl px-4 md:px-6 overflow-hidden">
                                <AccordionTrigger className="text-base md:text-lg font-semibold py-4 md:py-6 text-right hover:no-underline hover:text-primary transition-colors">
                                    {faq.question}
                                </AccordionTrigger>
                                <AccordionContent className="pb-4 md:pb-6 text-sm md:text-base text-muted-foreground leading-relaxed">
                                    {faq.answer}
                                </AccordionContent>
                            </AccordionItem>
                        ))}
                    </Accordion>
                </div>
            </div>
        </section>
    );
};
