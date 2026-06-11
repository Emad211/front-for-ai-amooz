'use client';

import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Quote, MessageCircle, ChevronLeft, ChevronRight } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';

/** Figma "testimonials" (node 277:521) — single centered quote with a slider. */
const TESTIMONIALS = [
  {
    content:
      'شب‌های امتحان همیشه یک سوال بی‌جواب داشتم و کسی نبود که ازش بپرسم. الان ساعت ۱۱ شب هم که روی یک مسئله گیر می‌کنم، دستیار هوشمند با چند روش مختلف برام حلش می‌کنه. ترازم تو چهار ماه از ۵۴۰۰ رسید به ۶۲۰۰ و روزی که کارنامه اومد، رتبه ۱۲۳ منطقه شدم.',
    name: 'آرش راد',
    role: 'رتبه ۱۲۳ کنکور ریاضی • دانش‌آموز سال گذشته',
    image: '',
  },
  {
    content:
      'من همیشه از ریاضی فراری بودم؛ کلاس جلو می‌رفت و من جا می‌موندم. مسیر یادگیری شخصی دقیقاً از همون نقطه‌ای شروع کرد که من رها کرده بودم، نه جلوتر و نه عقب‌تر. بعد از یک ترم، برای اولین بار تو زندگیم نمره‌ی ریاضی‌م بالای ۱۸ شد.',
    name: 'ستایش کریمی',
    role: 'دانش‌آموز پایه یازدهم • رشته ریاضی',
    image: '',
  },
  {
    content:
      'هر هفته شش ساعت فقط صرف طراحی سوال و تصحیح برگه می‌کردم. الان آزمون رو هوش مصنوعی از روی جزوه‌ی خودم می‌سازه، تصحیح و بازخوردش هم خودکاره. اون شش ساعت رو حالا می‌ذارم برای رفع اشکال تک‌تک بچه‌ها؛ و نمودار پیشرفت کلاس همیشه جلوی چشممه.',
    name: 'مریم موسوی',
    role: 'دبیر زیست‌شناسی • ۱۴ سال سابقه تدریس',
    image: '',
  },
  {
    content:
      'برای کلاس جبرانی و رفع اشکال خصوصی هزینه‌ی زیادی می‌دادیم و باز هم نتیجه نمی‌گرفتیم. سه ماهه که پسرم با AI-Amooz درس می‌خونه؛ خودش برنامه‌شو دنبال می‌کنه، آزمون می‌ده و من هر هفته گزارش پیشرفتش رو می‌بینم. معدلش از ۱۴ رسید به ۱۷/۵.',
    name: 'حمید عظیمی',
    role: 'پدر دانش‌آموز پایه دهم',
    image: '',
  },
];

export const TestimonialSection = ({ testimonialImage }: { testimonialImage?: { imageUrl?: string } }) => {
  const [index, setIndex] = useState(0);
  const active = TESTIMONIALS[index];
  const avatarSrc =
    (index === 0 && testimonialImage?.imageUrl ? testimonialImage.imageUrl : active.image) || undefined;

  const go = (dir: number) =>
    setIndex((i) => (i + dir + TESTIMONIALS.length) % TESTIMONIALS.length);

  return (
    <section className="relative overflow-hidden py-20 md:py-28">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute bottom-0 left-1/2 h-72 w-[36rem] -translate-x-1/2 rounded-full bg-primary/10 blur-[120px]" />
      </div>

      <div className="container mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mb-12 text-center"
        >
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary">
            <MessageCircle className="h-4 w-4" />
            نظرات
          </div>
        </motion.div>

        <div className="relative mx-auto max-w-4xl text-center">
          {/* Decorative quote glyphs flanking the quote (per Figma) */}
          <Quote
            aria-hidden
            className="pointer-events-none absolute -top-4 right-0 h-9 w-9 rotate-180 fill-current text-primary/30 md:-right-10"
          />
          <Quote
            aria-hidden
            className="pointer-events-none absolute bottom-24 left-0 h-14 w-14 fill-current text-primary/30 md:-left-10"
          />

          <div className="min-h-[18rem] sm:min-h-[14rem] md:min-h-[12rem]">
            <AnimatePresence mode="wait">
              <motion.p
                key={index}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }}
                transition={{ duration: 0.35 }}
                className="text-xl font-medium leading-9 text-foreground md:text-2xl md:leading-10"
              >
                {active.content}
              </motion.p>
            </AnimatePresence>
          </div>

          {/* Author */}
          <div className="mt-10 flex flex-col items-center gap-3">
            <Avatar className="h-16 w-16 border-2 border-primary/30">
              <AvatarImage src={avatarSrc} alt={active.name} />
              <AvatarFallback className="bg-primary/20 text-lg font-bold text-primary">
                {active.name[0]}
              </AvatarFallback>
            </Avatar>
            <div>
              <div className="text-lg font-bold text-foreground">{active.name}</div>
              <div className="text-sm text-muted-foreground">{active.role}</div>
            </div>
          </div>

          {/* Slider controls */}
          <div className="mt-10 flex items-center justify-center gap-6">
            <button
              type="button"
              onClick={() => go(-1)}
              aria-label="نظر قبلی"
              className="flex h-10 w-10 items-center justify-center rounded-full border border-border/60 text-muted-foreground transition-colors hover:border-primary/50 hover:text-primary"
            >
              <ChevronRight className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-2">
              {TESTIMONIALS.map((_, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setIndex(i)}
                  aria-label={`نظر ${i + 1}`}
                  className={`h-2 rounded-full transition-all ${
                    i === index ? 'w-6 bg-primary' : 'w-2 bg-border'
                  }`}
                />
              ))}
            </div>

            <button
              type="button"
              onClick={() => go(1)}
              aria-label="نظر بعدی"
              className="flex h-10 w-10 items-center justify-center rounded-full border border-border/60 text-muted-foreground transition-colors hover:border-primary/50 hover:text-primary"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>
    </section>
  );
};
