'use client';

import { motion } from 'framer-motion';
import { HelpCircle, MessageCircleQuestion } from 'lucide-react';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';

const FAQS = [
  {
    id: 'audience',
    question: 'AI-Amooz برای چه مقاطع و درس‌هایی مناسب است؟',
    answer: 'AI-Amooz برای طیف گسترده‌ای از درس‌ها و مقاطع قابل استفاده است. معلم محتوای خود را وارد می‌کند و پلتفرم همان محتوا را ساختاربندی و برای یادگیری آماده می‌کند.',
  },
  {
    id: 'free',
    question: 'آیا استفاده از دستیار هوشمند رایگان است؟',
    answer: 'شروع کار و تجربه‌ی قابلیت‌های پایه از مسیر ثبت‌نام در دسترس است. جزئیات امکانات و محدودیت‌ها در زمان ارائه‌ی پلن‌ها به‌صورت شفاف نمایش داده می‌شود.',
  },
  {
    id: 'personalized',
    question: 'چگونه مسیر یادگیری شخصی‌سازی می‌شود؟',
    answer: 'پلتفرم با بررسی فعالیت‌ها، نتایج آزمون و نقاط ضعف و قوت، ترتیب مناسب محتوا و تمرین را پیشنهاد می‌دهد و مسیر را با پیشرفت دانش‌آموز هماهنگ می‌کند.',
  },
  {
    id: 'mobile',
    question: 'آیا می‌توانم از موبایل استفاده کنم؟',
    answer: 'بله. رابط کاربری برای موبایل، تبلت و دسکتاپ طراحی شده است تا دانش‌آموز و معلم بتوانند از دستگاه‌های مختلف به مسیر خود ادامه دهند.',
  },
];

export const FAQSection = () => {
  return (
    <section id="faq" className="landing-section-shell h-[743px] px-2 pt-10 lg:h-[805px] lg:px-8 lg:py-10">
      <div className="landing-panel mx-auto h-[703px] w-full max-w-[424px] overflow-hidden px-2 pt-10 lg:h-[725px] lg:max-w-[1856px] lg:px-0">
        <motion.div initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center">
          <div className="mx-auto flex h-[38px] w-fit items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-[17px] text-sm font-medium text-primary">
            سوالات متداول
            <MessageCircleQuestion className="h-4 w-4" />
          </div>
          <h2 className="landing-display mt-8 h-[45px] text-[32px] font-black leading-[45px] text-foreground lg:h-[67px] lg:text-[48px] lg:leading-[67px]">
            پاسخ به سوالات شما
          </h2>
          <p className="mt-8 h-7 text-[16px] font-medium leading-7 text-muted-foreground lg:text-[20px]">
            اگر سوالی دارید، احتمالاً جوابش اینجاست
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          className="mx-auto mt-8 h-[360px] w-full max-w-[408px] lg:max-w-[768px]"
        >
          <Accordion type="single" collapsible className="space-y-4">
            {FAQS.map((faq) => (
              <AccordionItem
                key={faq.id}
                value={faq.id}
                className="group h-[78px] overflow-hidden rounded-2xl border border-border/60 bg-card/60 px-6 backdrop-blur-sm transition-all hover:border-primary/30 data-[state=open]:h-auto data-[state=open]:border-primary/40"
              >
                <AccordionTrigger className="h-[76px] py-0 text-right text-[16px] font-bold hover:no-underline lg:text-[18px]">
                  <span className="flex w-full items-center gap-3">
                    <HelpCircle className="h-5 w-5 shrink-0 text-primary/70" />
                    <span className="flex-1">{faq.question}</span>
                  </span>
                </AccordionTrigger>
                <AccordionContent className="pb-6 pe-8 text-sm leading-7 text-muted-foreground lg:text-base">
                  {faq.answer}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </motion.div>

        <p className="mx-auto mt-8 h-6 text-center text-[16px] leading-6 text-muted-foreground">
          سوال دیگری دارید؟{' '}
          <a href="mailto:info@ai-amooz.ir" className="font-semibold text-primary hover:underline">
            با ما تماس بگیرید
          </a>
        </p>
      </div>
    </section>
  );
};
