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

type TeacherFeature = {
  icon: LucideIcon;
  title: string;
  description: string;
  image: string;
  width: number;
  height: number;
  imageClassName?: string;
};

const TEACHER_FEATURES: TeacherFeature[] = [
  {
    icon: UsersRound,
    title: 'مدیریت کلاس و دانش‌آموزان',
    description:
      'کلاس‌ها، محتوای منتشرشده و وضعیت دانش‌آموزان را از یک فضای منظم مدیریت کنید.',
    image: '/landing/laptop-teacher-dark.png',
    width: 888,
    height: 641,
    imageClassName: 'max-w-[47rem]',
  },
  {
    icon: Sparkles,
    title: 'ساخت آزمون با هوش مصنوعی',
    description:
      'از روی محتوای آموزشی خود، آزمون و آمادگی آزمون بسازید و پیش‌نویس را پیش از انتشار بازبینی کنید.',
    image: '/landing/exam-builder-dark.png',
    width: 583,
    height: 304,
    imageClassName: 'max-w-[36rem] rounded-xl border border-white/10',
  },
  {
    icon: ClipboardCheck,
    title: 'تصحیح و نمره‌دهی هوشمند',
    description:
      'پاسخ‌ها با معیارهای معلم بررسی می‌شوند و برای هر دانش‌آموز بازخورد قابل بازبینی تولید می‌شود.',
    image: '/landing/quiz-sim-dark.png',
    width: 428,
    height: 221,
    imageClassName: 'max-w-[34rem] rounded-xl border border-white/10',
  },
  {
    icon: BarChart3,
    title: 'داشبورد تحلیل پیشرفت',
    description:
      'روند فعالیت، پیشرفت و نقاط نیازمند توجه را با نمودارها و شاخص‌های روشن دنبال کنید.',
    image: '/landing/mac-studio-dark.png',
    width: 792,
    height: 609,
    imageClassName: 'max-w-[44rem]',
  },
];

export const TeacherCtaSection = () => {
  const [activeIndex, setActiveIndex] = useState(2);
  const activeFeature = TEACHER_FEATURES[activeIndex];

  return (
    <section id="teacher-tools" className="landing-section-shell py-10 sm:py-14 lg:py-10">
      <div className="landing-wide-container">
        <div className="relative min-h-[48rem] overflow-hidden rounded-[1.25rem] bg-gradient-to-br from-emerald-600 to-teal-700 px-4 py-10 text-white shadow-[0_0_4px_hsl(var(--foreground)/.25)] sm:px-8 lg:min-h-[48rem] lg:px-24 lg:py-10">
          <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="absolute -bottom-48 -left-48 h-[40rem] w-[40rem] rounded-full bg-white/35 blur-[130px]" />
            <div className="absolute -right-40 -top-40 h-[32rem] w-[32rem] rounded-full bg-emerald-200/10 blur-[110px]" />
            <div className="absolute -bottom-[45rem] -right-[25rem] select-none text-[92rem] font-black leading-none text-white/[0.045]">*</div>
          </div>

          <div className="relative grid min-h-[42rem] items-center gap-10 lg:grid-cols-[1.08fr_.92fr] lg:gap-16">
            <motion.div
              initial={{ opacity: 0, x: -24 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: '-100px' }}
              transition={{ duration: 0.6 }}
              className="order-2 flex min-w-0 items-center justify-center lg:order-1"
            >
              <div className="relative flex min-h-[21rem] w-full items-center justify-center lg:min-h-[38rem]">
                <div className="absolute inset-x-8 bottom-8 h-16 rounded-full bg-white/30 blur-3xl" />
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeFeature.title}
                    initial={{ opacity: 0, x: -22, scale: 0.975 }}
                    animate={{ opacity: 1, x: 0, scale: 1 }}
                    exit={{ opacity: 0, x: 22, scale: 0.975 }}
                    transition={{ duration: 0.3, ease: 'easeOut' }}
                    className="relative flex w-full items-center justify-center"
                  >
                    <Image
                      src={activeFeature.image}
                      alt={activeFeature.title}
                      width={activeFeature.width}
                      height={activeFeature.height}
                      unoptimized
                      className={`h-auto w-full object-contain drop-shadow-[0_28px_45px_rgba(3,7,17,.45)] ${activeFeature.imageClassName ?? ''}`}
                    />
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
                    className={`flex aspect-square items-center justify-center rounded-2xl border transition-all ${
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
                      className={`group w-full rounded-2xl p-4 text-right transition-all duration-300 ${
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

              <div className="mt-7 min-h-24 text-center lg:hidden">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeFeature.title}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                  >
                    <h3 className="text-2xl font-black">{activeFeature.title}</h3>
                    <p className="mt-3 text-sm leading-7 text-white/85">{activeFeature.description}</p>
                  </motion.div>
                </AnimatePresence>
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
};
