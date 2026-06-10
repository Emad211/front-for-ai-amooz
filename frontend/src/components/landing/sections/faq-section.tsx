'use client';

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { motion } from 'framer-motion';
import { HelpCircle, MessageCircleQuestion } from 'lucide-react';

/** Figma "questions" (node 304:281) — four FAQs. */
const FAQS = [
  {
    id: 'audience',
    question: 'AI-Amooz برای چه مقاطع و درس‌هایی مناسب است؟',
    answer:
      'AI-Amooz برای همه‌ی مقاطع و درس‌ها طراحی شده؛ از دروس مدرسه تا آمادگی کنکور. کافی است محتوای درس را اضافه کنید تا پلتفرم آن را ساختاربندی و شخصی‌سازی کند.',
  },
  {
    id: 'free',
    question: 'آیا استفاده از دستیار هوشمند رایگان است؟',
    answer:
      'برای شروع می‌توانید به‌صورت رایگان ثبت‌نام کنید و دستیار هوشمند را امتحان کنید. برای امکانات پیشرفته‌تر، پلن‌های متنوعی در دسترس است.',
  },
  {
    id: 'personalized',
    question: 'چگونه مسیر یادگیری شخصی‌سازی می‌شود؟',
    answer:
      'هوش مصنوعی با سنجش سطح دانش و تحلیل نقاط ضعف و قوت شما، مسیر یادگیری اختصاصی می‌سازد و آن را در طول زمان بر اساس پیشرفت‌تان به‌روزرسانی می‌کند.',
  },
  {
    id: 'mobile',
    question: 'آیا می‌توانم از موبایل استفاده کنم؟',
    answer:
      'بله، AI-Amooz کاملاً واکنش‌گرا است و روی موبایل، تبلت و دسکتاپ به‌خوبی کار می‌کند؛ هر جا که باشید به یادگیری ادامه می‌دهید.',
  },
];

export const FAQSection = () => {
  return (
    <section id="faq" className="relative overflow-hidden py-20 md:py-28">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute right-1/4 top-10 h-72 w-72 rounded-full bg-primary/10 blur-[120px]" />
      </div>

      <div className="container mx-auto px-4">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mx-auto mb-12 max-w-3xl text-center md:mb-16"
        >
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary">
            <MessageCircleQuestion className="h-4 w-4" />
            سوالات متداول
          </div>
          <h2 className="mb-4 text-3xl font-black text-foreground md:text-5xl">
            پاسخ به سوالات شما
          </h2>
          <p className="text-base text-muted-foreground md:text-lg">
            اگر سوالی دارید، احتمالاً جوابش اینجاست
          </p>
        </motion.div>

        {/* Accordion */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mx-auto max-w-3xl"
        >
          <Accordion type="single" collapsible className="space-y-4">
            {FAQS.map((faq) => (
              <AccordionItem
                key={faq.id}
                value={faq.id}
                className="group overflow-hidden rounded-2xl border border-border/60 bg-card/60 px-5 backdrop-blur-sm transition-all duration-300 hover:border-primary/30 data-[state=open]:border-primary/40 md:px-6"
              >
                <AccordionTrigger className="py-5 text-right text-base font-bold transition-colors hover:no-underline group-hover:text-primary md:text-lg">
                  <div className="flex w-full items-center gap-3">
                    <HelpCircle className="h-5 w-5 flex-shrink-0 text-primary/60 transition-colors group-data-[state=open]:text-primary" />
                    <span className="flex-1">{faq.question}</span>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="pb-5 pr-8 text-sm leading-7 text-muted-foreground md:text-base">
                  {faq.answer}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </motion.div>

        {/* Contact line */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="mt-12 text-center"
        >
          <p className="text-muted-foreground">
            سوال دیگری دارید؟{' '}
            <a href="mailto:info@ai-amooz.ir" className="font-medium text-primary hover:underline">
              با ما تماس بگیرید
            </a>
          </p>
        </motion.div>
      </div>
    </section>
  );
};
