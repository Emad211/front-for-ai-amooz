'use client';

import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Quote, MessageCircle, ChevronLeft, ChevronRight } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';

/** Figma "testimonials" (node 277:521) — single centered quote with a slider. */
const TESTIMONIALS = [
  {
    content:
      'با AI-Amooz تونستم مفاهیم پیچیده ریاضی رو به سادگی یاد بگیرم. دستیار هوشمندش همیشه برای رفع اشکال کنارم بود و باعث شد با اعتماد به نفس بیشتری برای کنکور آماده بشم.',
    name: 'آرش راد',
    role: 'دانش‌آموز پایه دوازدهم • رتبه ۱۲۳ کنکور',
    image: '',
  },
  {
    content:
      'مسیر یادگیری شخصی‌سازی‌شده دقیقاً نقاط ضعفم رو هدف گرفت. تو سه ماه پیشرفتی داشتم که قبلاً تو یک سال هم به دست نیاورده بودم.',
    name: 'سارا محمدی',
    role: 'دانش‌آموز پایه یازدهم • رشته تجربی',
    image: '',
  },
  {
    content:
      'به‌عنوان معلم، ساخت آزمون و تصحیح خودکار کلی از وقتم رو آزاد کرد و حالا می‌تونم روی خودِ تدریس تمرکز کنم. تحلیل پیشرفت کلاس فوق‌العاده‌ست.',
    name: 'مهندس کریمی',
    role: 'دبیر ریاضی • ۱۲ سال سابقه تدریس',
    image: '',
  },
];

export const TestimonialSection = ({ testimonialImage }: { testimonialImage?: { imageUrl?: string } }) => {
  const [index, setIndex] = useState(0);
  const active = TESTIMONIALS[index];
  const avatarSrc = index === 0 && testimonialImage?.imageUrl ? testimonialImage.imageUrl : active.image;

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

        <div className="mx-auto max-w-4xl text-center">
          <Quote className="mx-auto mb-6 h-10 w-10 text-primary/40" />

          <div className="min-h-[10rem] md:min-h-[8rem]">
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
