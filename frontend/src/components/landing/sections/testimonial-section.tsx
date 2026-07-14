'use client';

import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ChevronLeft, ChevronRight, MessageCircle, Quote } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';

const TESTIMONIALS = [
  {
    content:
      'با AI-Amooz تونستم مفاهیم پیچیده ریاضی رو به سادگی یاد بگیرم. دستیار هوشمندش همیشه برای رفع اشکال کنارم بود و باعث شد با اعتماد به نفس بیشتری برای کنکور آماده بشم.',
    name: 'آرش راد',
    role: 'دانش‌آموز پایه دوازدهم • رتبه ۱۲۳ کنکور',
    image: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?q=80&w=160&h=160&auto=format&fit=crop',
  },
  {
    content:
      'مسیر یادگیری شخصی‌سازی‌شده کمک کرد دقیقاً روی مباحثی تمرکز کنم که در آن‌ها ضعف داشتم و هر مرحله را با تمرین و بازخورد جلو ببرم.',
    name: 'ثنا جاوید',
    role: 'دانش‌آموز پایه یازدهم تجربی',
    image: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?q=80&w=160&h=160&auto=format&fit=crop',
  },
  {
    content:
      'ساخت تمرین، بررسی پاسخ‌ها و دیدن روند پیشرفت کلاس در یک پنل، زمان کارهای تکراری را کمتر کرده و فرصت بیشتری برای بازخورد مستقیم می‌دهد.',
    name: 'مریم موسوی',
    role: 'دبیر زیست‌شناسی',
    image: 'https://images.unsplash.com/photo-1551836022-d5d88e9218df?q=80&w=160&h=160&auto=format&fit=crop',
  },
] as const;

export const TestimonialSection = () => {
  const [index, setIndex] = useState(0);
  const active = TESTIMONIALS[index] ?? TESTIMONIALS[0]!;
  const go = (direction: number) =>
    setIndex((current) => (current + direction + TESTIMONIALS.length) % TESTIMONIALS.length);

  return (
    <section className="landing-section-shell h-[772px] px-2 pt-10 lg:h-[768px] lg:p-0">
      <div className="relative mx-auto h-[732px] w-full max-w-[424px] overflow-hidden lg:h-[768px] lg:max-w-[1920px]">
        <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute bottom-0 left-1/2 h-72 w-[40rem] -translate-x-1/2 rounded-full bg-primary/10 blur-[130px]" />
        </div>

        <div className="absolute left-1/2 top-[104px] flex h-[38px] -translate-x-1/2 items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-[17px] text-sm font-medium text-primary lg:top-[186px]">
          نظرات
          <MessageCircle className="h-[19px] w-[19px]" />
        </div>

        <div className="absolute inset-x-2 top-[174px] h-[366px] lg:inset-x-32 lg:top-[256px] lg:h-[326px]">
          <Quote aria-hidden className="absolute -right-2 -top-[68px] h-8 w-8 rotate-180 fill-current text-primary/25 lg:right-[19%] lg:top-[-58px]" />
          <Quote aria-hidden className="absolute bottom-9 left-8 h-[51px] w-[51px] fill-current text-primary/25 lg:bottom-[95px] lg:left-[16%]" />

          <div className="flex h-[190px] items-center justify-center lg:h-[150px]">
            <AnimatePresence mode="wait">
              <motion.blockquote
                key={index}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                transition={{ duration: 0.3 }}
                className="max-w-[408px] text-center text-[20px] font-medium leading-[1.9] text-foreground lg:max-w-[994px] lg:text-[32px] lg:leading-[1.55]"
              >
                {active.content}
              </motion.blockquote>
            </AnimatePresence>
          </div>

          <div className="absolute inset-x-0 bottom-0 flex h-[120px] flex-col items-center gap-2">
            <Avatar className="h-16 w-16 border-2 border-primary/30">
              <AvatarImage src={active.image} alt={active.name} />
              <AvatarFallback className="bg-primary/15 text-lg font-bold text-primary">{active.name[0]}</AvatarFallback>
            </Avatar>
            <strong className="text-lg text-foreground">{active.name}</strong>
            <span className="text-sm text-muted-foreground">{active.role}</span>
          </div>
        </div>

        <div className="absolute bottom-8 left-1/2 flex h-8 -translate-x-1/2 items-center justify-center gap-5 lg:bottom-[12px]">
          <button type="button" onClick={() => go(-1)} aria-label="نظر قبلی" className="text-muted-foreground transition-colors hover:text-primary">
            <ChevronRight className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-3">
            {TESTIMONIALS.map((_, itemIndex) => (
              <button
                key={itemIndex}
                type="button"
                onClick={() => setIndex(itemIndex)}
                aria-label={`نظر ${itemIndex + 1}`}
                className={`h-2 rounded-full transition-all ${itemIndex === index ? 'w-5 bg-primary' : 'w-2 bg-border'}`}
              />
            ))}
          </div>
          <button type="button" onClick={() => go(1)} aria-label="نظر بعدی" className="text-muted-foreground transition-colors hover:text-primary">
            <ChevronLeft className="h-5 w-5" />
          </button>
        </div>
      </div>
    </section>
  );
};
