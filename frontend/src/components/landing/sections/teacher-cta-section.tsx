'use client';

import { useState } from 'react';
import Image from 'next/image';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Users,
  Wand2,
  PenLine,
  LineChart,
  type LucideIcon,
} from 'lucide-react';

/**
 * Teacher CTA — Figma "1920w dark redesign" (تدریست رو با هوش مصنوعی متحول کن).
 * The four feature rows are interactive tabs: selecting one crossfades the
 * device screenshot on the other side and expands a short description under
 * the row. Mobile (per the Figma mobile design) shows the four features as a
 * row of icon tiles above the image, with the active feature's text below it.
 */
type Feature = {
  icon: LucideIcon;
  title: string;
  description: string;
  image: string;
  imageWidth: number;
  imageHeight: number;
  /** true when the asset is a bare UI panel that needs its own frame */
  panel?: boolean;
};

const FEATURES: Feature[] = [
  {
    icon: Users,
    title: 'مدیریت کلاس و دانش‌آموزان',
    description:
      'همه‌ی کلاس‌ها و دانش‌آموزانت را در یک پنل منظم ببین؛ دعوت با کد کلاس، دسته‌بندی دوره‌ها و پیگیری لحظه‌ای فعالیت‌ها.',
    image: '/landing/laptop-teacher-dark.png',
    imageWidth: 888,
    imageHeight: 641,
  },
  {
    icon: Wand2,
    title: 'ساخت آزمون با هوش مصنوعی',
    description:
      'از روی جزوه و محتوای خودِ کلاس، در چند دقیقه آزمون استاندارد بساز؛ چندگزینه‌ای، جای خالی و تشریحی با سطح‌بندی دلخواه.',
    image: '/landing/exam-builder-dark.png',
    imageWidth: 583,
    imageHeight: 304,
    panel: true,
  },
  {
    icon: PenLine,
    title: 'تصحیح و نمره‌دهی خودکار',
    description:
      'پاسخ‌ها را هوش مصنوعی تصحیح می‌کند و برای هر دانش‌آموز بازخورد جداگانه می‌نویسد؛ بدون یک برگه تصحیح دستی.',
    image: '/landing/quiz-sim-dark.png',
    imageWidth: 428,
    imageHeight: 187,
    panel: true,
  },
  {
    icon: LineChart,
    title: 'داشبورد تحلیل پیشرفت',
    description:
      'روند پیشرفت هر دانش‌آموز و میانگین کلاس را با نمودارهای دقیق دنبال کن و نقاط ضعف مشترک را زود تشخیص بده.',
    image: '/landing/mac-studio-dark.png',
    imageWidth: 792,
    imageHeight: 609,
  },
];

export const TeacherCtaSection = () => {
  const [activeIndex, setActiveIndex] = useState(0);
  const active = FEATURES[activeIndex];

  const screenshot = (
    <AnimatePresence mode="wait">
      <motion.div
        key={activeIndex}
        initial={{ opacity: 0, x: -24, scale: 0.97 }}
        animate={{ opacity: 1, x: 0, scale: 1 }}
        exit={{ opacity: 0, x: 24, scale: 0.97 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
        className="flex w-full items-center justify-center"
      >
        <Image
          src={active.image}
          alt={active.title}
          width={active.imageWidth}
          height={active.imageHeight}
          unoptimized
          className={`h-auto w-full drop-shadow-2xl ${
            active.panel
              ? 'max-w-md rounded-2xl border border-white/10 bg-[#030711]/40 shadow-2xl'
              : 'max-w-lg'
          }`}
        />
      </motion.div>
    </AnimatePresence>
  );

  return (
    <section className="relative overflow-hidden py-20 md:py-28">
      <div className="sm:container sm:mx-auto sm:px-4">
        <div className="relative overflow-hidden bg-gradient-to-br from-emerald-600 to-teal-700 p-6 py-12 shadow-2xl sm:rounded-3xl md:p-12">
          {/* Ambient glow */}
          <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-emerald-300/20 blur-[100px]" />
          <div className="pointer-events-none absolute -bottom-24 -left-20 h-72 w-72 rounded-full bg-teal-200/10 blur-[100px]" />

          <div className="relative grid items-center gap-10 lg:grid-cols-2">
            {/* Screenshot (left in RTL) */}
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.6 }}
              className="order-last lg:order-first"
            >
              <div className="mx-auto flex min-h-[16rem] w-full max-w-lg items-center justify-center md:min-h-[22rem]">
                {screenshot}
              </div>

              {/* Mobile: active feature text under the image (per Figma mobile) */}
              <div className="mt-8 text-center text-white lg:hidden">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeIndex}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.25 }}
                  >
                    <h3 className="text-xl font-black">{active.title}</h3>
                    <p className="mx-auto mt-3 max-w-sm text-sm leading-7 text-white/80">
                      {active.description}
                    </p>
                  </motion.div>
                </AnimatePresence>
              </div>
            </motion.div>

            {/* Text + interactive feature list (right in RTL) */}
            <motion.div
              initial={{ opacity: 0, x: 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.6 }}
              className="text-center text-white lg:text-right"
            >
              <h2 className="text-3xl font-black leading-snug md:text-4xl">
                تدریست رو با هوش مصنوعی متحول کن
              </h2>
              <p className="mt-4 text-sm leading-7 text-white/80 md:text-base">
                همون موتور هوشمندی که کنار دانش‌آموزهاست، حالا ابزارهای حرفه‌ای رو هم در اختیار
                معلم‌ها می‌ذاره؛ از ساخت آزمون و تصحیح خودکار تا تحلیل دقیق پیشرفت کلاس.
              </p>

              {/* Mobile: four icon tiles in a row (per Figma mobile) */}
              <div className="mt-8 flex justify-center gap-3 lg:hidden">
                {FEATURES.map((feature, index) => (
                  <button
                    key={feature.title}
                    type="button"
                    aria-pressed={index === activeIndex}
                    aria-label={feature.title}
                    onClick={() => setActiveIndex(index)}
                    className={`flex h-14 w-14 items-center justify-center rounded-2xl transition-all duration-300 ${
                      index === activeIndex
                        ? 'scale-110 bg-white/25 shadow-lg shadow-emerald-900/40'
                        : 'bg-[#030711]/15 hover:bg-[#030711]/25'
                    }`}
                  >
                    <feature.icon className="h-6 w-6" />
                  </button>
                ))}
              </div>

              {/* Desktop: clickable feature rows — active one expands + swaps the screenshot */}
              <ul className="mt-8 hidden space-y-3 lg:block">
                {FEATURES.map((feature, index) => {
                  const isActive = index === activeIndex;
                  return (
                    <motion.li
                      key={feature.title}
                      initial={{ opacity: 0, y: 16 }}
                      whileInView={{ opacity: 1, y: 0 }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.4, delay: index * 0.08 }}
                    >
                      <button
                        type="button"
                        aria-pressed={isActive}
                        onClick={() => setActiveIndex(index)}
                        className={`w-full rounded-2xl p-4 text-right transition-colors duration-300 ${
                          isActive
                            ? 'bg-white/15 shadow-lg shadow-emerald-900/30'
                            : 'bg-[#030711]/15 hover:bg-[#030711]/25'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <span
                            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-colors duration-300 ${
                              isActive ? 'bg-white/20' : 'bg-white/10'
                            } text-white`}
                          >
                            <feature.icon className="h-5 w-5" />
                          </span>
                          <span className="font-semibold">{feature.title}</span>
                        </div>
                        <AnimatePresence initial={false}>
                          {isActive && (
                            <motion.p
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              transition={{ duration: 0.3, ease: 'easeOut' }}
                              className="overflow-hidden pr-[3.25rem] text-sm leading-6 text-white/75"
                            >
                              <span className="block pt-2">{feature.description}</span>
                            </motion.p>
                          )}
                        </AnimatePresence>
                      </button>
                    </motion.li>
                  );
                })}
              </ul>
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
};
