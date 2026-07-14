'use client';

import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ChevronLeft, ChevronRight, MessageCircle, Quote } from 'lucide-react';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';

const TESTIMONIALS = [
  {
    content:
      'وقتی در یک مبحث گیر می‌کنم، دستیار هوشمند همان موضوع را مرحله‌به‌مرحله توضیح می‌دهد و کمک می‌کند بدون رهاکردن مسیر، تمرین را ادامه بدهم.',
    name: 'دانش‌آموز دوازدهم',
    role: 'سناریوی نمونهٔ استفاده',
  },
  {
    content:
      'مسیر یادگیری از همان نقطه‌ای شروع می‌شود که مشکل دارم؛ درس‌ها منظم‌تر جلو می‌روند و می‌توانم پیشرفت خودم را در طول دوره ببینم.',
    name: 'دانش‌آموز یازدهم',
    role: 'سناریوی نمونهٔ استفاده',
  },
  {
    content:
      'ساخت تمرین و بررسی وضعیت کلاس در یک فضای واحد، زمان کارهای تکراری را کمتر می‌کند و فرصت بیشتری برای بازخورد مستقیم به دانش‌آموزان می‌دهد.',
    name: 'دبیر زیست‌شناسی',
    role: 'سناریوی نمونهٔ استفاده',
  },
] as const;

export const TestimonialSection = () => {
  const [index, setIndex] = useState(0);
  const active = TESTIMONIALS[index] ?? TESTIMONIALS[0];
  const go = (direction: number) =>
    setIndex((current) => (current + direction + TESTIMONIALS.length) % TESTIMONIALS.length);

  return (
    <section className="landing-section-shell relative min-h-[46rem] px-4 py-20 lg:min-h-[48rem] lg:px-8 lg:py-40">
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute bottom-0 left-1/2 h-72 w-[40rem] -translate-x-1/2 rounded-full bg-primary/10 blur-[130px]" />
      </div>

      <div className="relative mx-auto flex w-full max-w-[1664px] flex-col items-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-[17px] py-[9px] text-sm font-medium text-primary">
          تجربهٔ استفاده
          <MessageCircle className="h-5 w-5" />
        </div>

        <div className="relative mt-8 flex w-full max-w-[62rem] flex-col items-center text-center">
          <Quote aria-hidden className="absolute -right-2 -top-3 h-9 w-9 rotate-180 fill-current text-primary/20 sm:-right-10" />
          <Quote aria-hidden className="absolute -bottom-6 -left-2 h-14 w-14 fill-current text-primary/20 sm:-left-10" />

          <div className="flex min-h-[14rem] items-center justify-center sm:min-h-[12rem]">
            <AnimatePresence mode="wait">
              <motion.blockquote
                key={index}
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -14 }}
                transition={{ duration: 0.32 }}
                className="text-xl font-medium leading-[2.15] text-foreground sm:text-2xl lg:text-3xl"
              >
                {active.content}
              </motion.blockquote>
            </AnimatePresence>
          </div>

          <div className="mt-8 flex flex-col items-center gap-2">
            <Avatar className="h-16 w-16 border-2 border-primary/30">
              <AvatarFallback className="bg-primary/15 text-lg font-bold text-primary">
                {active.name.slice(0, 1)}
              </AvatarFallback>
            </Avatar>
            <strong className="mt-1 text-lg text-foreground">{active.name}</strong>
            <span className="text-sm text-muted-foreground">{active.role}</span>
          </div>

          <div className="mt-14 flex items-center justify-center gap-6">
            <button
              type="button"
              onClick={() => go(-1)}
              aria-label="تجربه قبلی"
              className="flex h-10 w-10 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
            <div className="flex items-center gap-3">
              {TESTIMONIALS.map((_, itemIndex) => (
                <button
                  key={itemIndex}
                  type="button"
                  onClick={() => setIndex(itemIndex)}
                  aria-label={`تجربه ${itemIndex + 1}`}
                  className={`h-2 rounded-full transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                    itemIndex === index ? 'w-5 bg-primary' : 'w-2 bg-border'
                  }`}
                />
              ))}
            </div>
            <button
              type="button"
              onClick={() => go(1)}
              aria-label="تجربه بعدی"
              className="flex h-10 w-10 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>
    </section>
  );
};
