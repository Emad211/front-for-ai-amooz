'use client';

import Image from 'next/image';
import { AnimatePresence, motion } from 'framer-motion';
import { useState } from 'react';
import {
  BarChart3,
  ClipboardCheck,
  Sparkles,
  UsersRound,
  type LucideIcon,
} from 'lucide-react';
import { TEACHER_PRODUCT_ASSETS } from '@/components/landing/teacher-product-assets';

type TeacherFeature = {
  icon: LucideIcon;
  title: string;
  description: string;
  image: {
    src: string;
    alt: string;
    width: number;
    height: number;
  };
  imageClassName?: string;
};

const TEACHER_FEATURES: TeacherFeature[] = [
  {
    icon: UsersRound,
    title: 'مدیریت کلاس و دانش‌آموزان',
    description:
      'کلاس، فصل‌ها، محتوای منتشرشده و وضعیت دانش‌آموزان را از یک نمای منظم مدیریت و بازبینی کنید.',
    image: TEACHER_PRODUCT_ASSETS.classOverview,
    imageClassName: 'object-top',
  },
  {
    icon: Sparkles,
    title: 'ساخت آزمون با هوش مصنوعی',
    description:
      'فایل حل تست را وارد کنید تا ترنسکریپت و سؤال‌ها استخراج شوند؛ پیش‌نویس را پیش از انتشار خودتان بازبینی کنید.',
    image: TEACHER_PRODUCT_ASSETS.examPrep,
    imageClassName: 'object-top',
  },
  {
    icon: ClipboardCheck,
    title: 'تصحیح و نمره‌دهی هوشمند',
    description:
      'تمرین، پاسخ‌نامه و بارم را تعریف کنید؛ پاسخ‌ها با معیارهای شما بررسی می‌شوند و بازخورد قابل بازبینی تولید می‌شود.',
    image: TEACHER_PRODUCT_ASSETS.exercise,
    imageClassName: 'object-top',
  },
  {
    icon: BarChart3,
    title: 'داشبورد تحلیل پیشرفت',
    description:
      'تعداد کلاس‌ها و دانش‌آموزان، فعالیت‌ها و روند رشد را با شاخص‌ها و نمودارهای روشن زیر نظر بگیرید.',
    image: TEACHER_PRODUCT_ASSETS.analytics,
    imageClassName: 'object-top',
  },
];

export const TeacherCtaSection = () => {
  const [activeIndex, setActiveIndex] = useState(2);
  const activeFeature = TEACHER_FEATURES[activeIndex] ?? TEACHER_FEATURES[0]!;

  return (
    <section id="teacher-tools" className="landing-section-shell py-10 sm:py-14 lg:py-10">
      <div className="landing-wide-container">
        <div className="relative min-h-[787px] overflow-hidden rounded-[1.25rem] bg-gradient-to-br from-emerald-600 to-teal-700 px-4 py-10 text-white shadow-[0_0_4px_hsl(var(--foreground)/.25)] sm:px-8 lg:min-h-[48rem] lg:px-24 lg:py-10">
          <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="absolute -bottom-48 -left-48 h-[40rem] w-[40rem] rounded-full bg-white/35 blur-[130px]" />
            <div className="absolute -right-40 -top-40 h-[32rem] w-[32rem] rounded-full bg-emerald-200/10 blur-[110px]" />
            <div className="absolute -bottom-[45rem] -right-[25rem] select-none text-[92rem] font-black leading-none text-white/[0.045]">*</div>
          </div>

          <div className="relative grid items-center gap-8 lg:min-h-[42rem] lg:grid-cols-[1.08fr_.92fr] lg:gap-16">
            <motion.div
              initial={{ opacity: 0, x: -24 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: '-100px' }}
              transition={{ duration: 0.6 }}
              className="order-2 min-w-0 lg:order-1"
            >
              <div className="relative mx-auto flex w-full max-w-[54rem] items-center justify-center lg:min-h-[38rem]">
                <div className="absolute inset-x-8 bottom-3 h-20 rounded-full bg-white/30 blur-3xl lg:bottom-8" />
                <div className="absolute -inset-5 rounded-[2rem] bg-[#030711]/20 blur-2xl" />

                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeFeature.title}
                    initial={{ opacity: 0, x: -22, scale: 0.975 }}
                    animate={{ opacity: 1, x: 0, scale: 1 }}
                    exit={{ opacity: 0, x: 22, scale: 0.975 }}
                    transition={{ duration: 0.3, ease: 'easeOut' }}
                    className="relative w-full"
                  >
                    <div className="overflow-hidden rounded-[1.15rem] border border-white/20 bg-[#030711] p-1.5 shadow-[0_30px_65px_rgba(3,7,17,.5)] sm:p-2">
                      <div className="relative aspect-video overflow-hidden rounded-[.85rem] bg-[#030711]">
                        <Image
                          src={activeFeature.image.src}
                          alt={activeFeature.image.alt}
                          fill
                          sizes="(max-width: 1023px) 92vw, 52vw"
                          quality={90}
                          priority={activeIndex === 2}
                          className={`object-cover ${activeFeature.imageClassName ?? ''}`}
                        />
                        <div className="pointer-events-none absolute inset-0 ring-1 ring-inset ring-white/5" />
                      </div>
                    </div>
                  </motion.div>
                </AnimatePresence>
              </div>

              <div className="mt-7 min-h-24 text-center lg:hidden">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeFeature.title}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.25 }}
                  >
                    <h3 className="text-2xl font-black">{activeFeature.title}</h3>
                    <p className="mx-auto mt-3 max-w-md text-sm leading-7 text-white/85">
                      {activeFeature.description}
                    </p>
                  </motion.div>
                </AnimatePresence>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 24 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: '-100px' }}
              transition={{ duration: 0.6 }}
              className="order-1 text-center lg:order-2 lg:text-right"
            >
              <div className="mb-6 inline-flex items-center gap-2 rounded-full bg-[#030711] px-4 py-2 text-sm font-medium text-white">
                <span>مخصوص دبیران</span>
                <Sparkles className="h-5 w-5" />
              </div>

              <h2 className="landing-display text-4xl font-black leading-[1.25] sm:text-5xl lg:text-6xl">
                تدریست رو با هوش مصنوعی متحول کن
              </h2>
              <p className="mt-6 text-base font-medium leading-8 text-white/85 sm:text-lg lg:max-w-3xl lg:text-xl">
                همان موتور هوشمندی که کنار دانش‌آموزهاست، ابزارهای حرفه‌ای ساخت محتوا، تمرین، آزمون و تحلیل کلاس را هم در اختیار معلم قرار می‌دهد.
              </p>

              <div className="mt-8 grid grid-cols-4 gap-2 lg:hidden">
                {TEACHER_FEATURES.map((feature, index) => (
                  <button
                    key={feature.title}
                    type="button"
                    aria-label={feature.title}
                    aria-pressed={index === activeIndex}
                    onClick={() => setActiveIndex(index)}
                    className={`flex aspect-square min-h-14 items-center justify-center rounded-2xl border transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 ${
                      index === activeIndex
                        ? 'scale-[1.04] border-white/30 bg-white/20 shadow-lg'
                        : 'border-transparent bg-[#030711]/15 text-white/75'
                    }`}
                  >
                    <feature.icon className="h-6 w-6" />
                  </button>
                ))}
              </div>

              <div className="mt-8 hidden flex-col lg:flex">
                {TEACHER_FEATURES.map((feature, index) => {
                  const isActive = index === activeIndex;
                  return (
                    <button
                      key={feature.title}
                      type="button"
                      aria-pressed={isActive}
                      onMouseEnter={() => setActiveIndex(index)}
                      onFocus={() => setActiveIndex(index)}
                      onClick={() => setActiveIndex(index)}
                      className={`group w-full rounded-2xl p-4 text-right transition-all duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 ${
                        isActive
                          ? 'border-2 border-white/20 bg-white/15 shadow-[0_5px_14px_rgba(0,0,0,.10)] backdrop-blur-xl'
                          : 'border-2 border-transparent hover:bg-[#030711]/10'
                      }`}
                    >
                      <span className="flex items-center gap-6">
                        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[#030711]/15">
                          <feature.icon className="h-6 w-6" />
                        </span>
                        <span className="text-2xl font-bold">{feature.title}</span>
                      </span>
                      <AnimatePresence initial={false}>
                        {isActive && (
                          <motion.span
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.25 }}
                            className="block overflow-hidden pe-[4.5rem]"
                          >
                            <span className="block pt-4 text-base leading-7 text-white/90">
                              {feature.description}
                            </span>
                          </motion.span>
                        )}
                      </AnimatePresence>
                    </button>
                  );
                })}
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
};
