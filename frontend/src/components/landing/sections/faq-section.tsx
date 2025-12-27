'use client';

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";

export const FAQSection = () => (
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
                    <AccordionItem value="item-1" className="bg-card/50 border border-border/50 rounded-xl md:rounded-2xl px-4 md:px-6 overflow-hidden">
                        <AccordionTrigger className="text-base md:text-lg font-semibold py-4 md:py-6 text-right hover:no-underline hover:text-primary transition-colors">
                            AI-Amooz برای چه مقاطع و درس‌هایی مناسب است؟
                        </AccordionTrigger>
                        <AccordionContent className="pb-4 md:pb-6 text-sm md:text-base text-muted-foreground leading-relaxed">
                            در حال حاضر روی دروس تخصصی متوسطه دوم (ریاضیات، فیزیک و علوم کامپیوتر) متمرکز هستیم. 
                            به طور مداوم در حال گسترش محتوا برای رشته‌ها و مقاطع بیشتر هستیم.
                        </AccordionContent>
                    </AccordionItem>
                    
                    <AccordionItem value="item-2" className="bg-card/50 border border-border/50 rounded-xl md:rounded-2xl px-4 md:px-6 overflow-hidden">
                        <AccordionTrigger className="text-base md:text-lg font-semibold py-4 md:py-6 text-right hover:no-underline hover:text-primary transition-colors">
                            آیا استفاده از دستیار هوشمند رایگان است؟
                        </AccordionTrigger>
                        <AccordionContent className="pb-4 md:pb-6 text-sm md:text-base text-muted-foreground leading-relaxed">
                            بله! ثبت‌نام و استفاده از بخش قابل توجهی از امکانات رایگان است. 
                            برای دسترسی نامحدود، پلن‌های اشتراک مقرون‌به‌صرفه داریم.
                        </AccordionContent>
                    </AccordionItem>
                    
                    <AccordionItem value="item-3" className="bg-card/50 border border-border/50 rounded-xl md:rounded-2xl px-4 md:px-6 overflow-hidden">
                        <AccordionTrigger className="text-base md:text-lg font-semibold py-4 md:py-6 text-right hover:no-underline hover:text-primary transition-colors">
                            چگونه مسیر یادگیری شخصی‌سازی می‌شود؟
                        </AccordionTrigger>
                        <AccordionContent className="pb-4 md:pb-6 text-sm md:text-base text-muted-foreground leading-relaxed">
                            با یک آزمون تعیین سطح اولیه، نقاط قوت و ضعف شما شناسایی می‌شود. 
                            سپس با تحلیل مداوم عملکرد، نقشه راه به‌روزرسانی می‌شود.
                        </AccordionContent>
                    </AccordionItem>
                    
                    <AccordionItem value="item-4" className="bg-card/50 border border-border/50 rounded-xl md:rounded-2xl px-4 md:px-6 overflow-hidden">
                        <AccordionTrigger className="text-base md:text-lg font-semibold py-4 md:py-6 text-right hover:no-underline hover:text-primary transition-colors">
                            آیا می‌توانم از موبایل استفاده کنم؟
                        </AccordionTrigger>
                        <AccordionContent className="pb-4 md:pb-6 text-sm md:text-base text-muted-foreground leading-relaxed">
                            بله! پلتفرم کاملاً ریسپانسیو است و می‌توانید از هر دستگاهی استفاده کنید. 
                            اپلیکیشن موبایل هم به زودی منتشر می‌شود.
                        </AccordionContent>
                    </AccordionItem>
                </Accordion>
            </div>
        </div>
    </section>
);
