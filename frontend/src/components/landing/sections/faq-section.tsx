'use client';

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
    <section id="faq" className="landing-section-shell px-2 pt-10 md:px-8 md:py-10">
      <div className="landing-panel mx-auto flex w-full max-w-[424px] flex-col items-center px-2 py-10 md:max-w-[1856px] md:px-0">
        <div className="mx-auto flex h-[38px] w-fit items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-[17px] text-sm font-medium text-primary">
          سوالات متداول
          <MessageCircleQuestion className="h-4 w-4" />
        </div>

        <h2 className="landing-display mt-8 text-center text-[32px] font-black leading-[45px] text-foreground md:text-[clamp(36px,2.5vw,48px)] md:leading-[1.4]">
          پاسخ به سوالات شما
        </h2>

        <p className="mx-auto mt-8 max-w-[777px] px-2 text-center text-[16px] font-medium leading-7 text-muted-foreground md:px-0 md:text-[clamp(17px,1.05vw,20px)]">
          اگر سوالی دارید، احتمالاً جوابش اینجاست
        </p>

        <div className="mx-auto mt-8 w-full max-w-[408px] md:max-w-[768px]">
          <Accordion type="single" collapsible className="space-y-4">
            {FAQS.map((faq) => (
              <AccordionItem
                key={faq.id}
                value={faq.id}
                className="group min-h-[78px] overflow-hidden rounded-2xl border border-border/60 bg-card/60 px-5 backdrop-blur-sm transition-[border-color,background-color,box-shadow] hover:border-primary/30 data-[state=open]:border-primary/50 data-[state=open]:bg-card/80 data-[state=open]:shadow-[0_14px_34px_hsl(var(--background)/.22)] sm:px-6"
              >
                <AccordionTrigger className="min-h-[76px] py-4 text-right text-[14px] font-bold leading-6 hover:no-underline sm:text-[15px] md:text-[18px] md:leading-7">
                  <span className="flex min-w-0 flex-1 items-center gap-3">
                    <HelpCircle className="h-5 w-5 shrink-0 text-primary" />
                    <span className="min-w-0 flex-1 whitespace-normal break-words text-right">{faq.question}</span>
                  </span>
                </AccordionTrigger>
                <AccordionContent className="pb-6 pe-8 ps-1 text-right text-[14px] leading-7 text-muted-foreground sm:pe-10 md:text-base md:leading-8">
                  {faq.answer}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>

        <p className="mx-auto mt-8 px-2 text-center text-[15px] leading-6 text-muted-foreground sm:text-[16px]">
          سوال دیگری دارید؟{' '}
          <a href="mailto:info@ai-amooz.ir" className="font-semibold text-primary underline-offset-4 hover:underline">
            با ما تماس بگیرید
          </a>
        </p>
      </div>
    </section>
  );
};
