'use client';

import Image from 'next/image';
import { motion } from 'framer-motion';
import { Bot, Brain, Settings } from 'lucide-react';

const cardBase =
  'group relative overflow-hidden rounded-3xl border border-white/10 text-white shadow-xl transition-all duration-500 hover:shadow-2xl';

/**
 * Features bento — Figma "1920w dark redesign" (همه چیز در یک مکان).
 * Card gradients and the real dark UI screenshots come straight from the design:
 * purple tall (smart assistant phone), rose wide (AI exam builder), and a
 * half-width bottom row — green (Konkur simulator) + orange (learning stages),
 * side by side even on mobile.
 */
export const FeaturesSection = () => {
  return (
    <section id="features" className="relative overflow-hidden py-20 md:py-28">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-1/2 top-0 h-80 w-[40rem] -translate-x-1/2 rounded-full bg-primary/10 blur-[120px]" />
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
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/40 bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary">
            <Settings className="h-4 w-4" />
            ویژگی‌ها
          </div>
          <h2 className="mb-4 text-3xl font-black text-foreground md:text-5xl">
            همه چیز در یک مکان
          </h2>
          <p className="text-base text-muted-foreground md:text-lg">
            همه چیزی که از یک ابزار یادگیری نیاز دارید، یکجا و هوشمند
          </p>
        </motion.div>

        {/* Bento grid */}
        <div
          dir="ltr"
          className="mx-auto grid max-w-6xl grid-cols-2 gap-4 md:gap-5 lg:grid-cols-3 lg:grid-rows-2"
        >
          {/* A — Smart assistant (purple, tall) */}
          <motion.div
            dir="rtl"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-50px' }}
            transition={{ duration: 0.5 }}
            className={`${cardBase} col-span-2 flex flex-col bg-gradient-to-br from-violet-600 to-purple-700 p-6 md:p-8 lg:col-span-1 lg:col-start-1 lg:row-span-2 lg:row-start-1`}
          >
            <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-white/15">
              <Bot className="h-6 w-6" />
            </div>
            <h3 className="mb-2 text-xl font-bold md:text-2xl">دستیار هوشمند</h3>
            <p className="mb-6 text-sm leading-7 text-white/75">
              هر لحظه که سوالی داشتی، کنارت است؛ رفع اشکال، توضیح گام‌به‌گام و راه‌حل‌های جایگزین.
            </p>
            <div className="relative mx-auto mt-auto w-40 sm:w-48">
              <Image
                src="/landing/iphone-chat-dark.png"
                alt="دستیار هوشمند AI-Amooz"
                width={243}
                height={525}
                className="h-auto w-full drop-shadow-2xl"
              />
            </div>
            <div className="absolute -bottom-16 -left-10 h-44 w-44 rounded-full bg-white/10 blur-2xl transition-opacity duration-500 group-hover:opacity-80" />
          </motion.div>

          {/* B — AI online exams (rose, wide top) */}
          <motion.div
            dir="rtl"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-50px' }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className={`${cardBase} col-span-2 flex flex-col gap-6 bg-gradient-to-br from-rose-600 to-pink-700 p-6 md:p-8 lg:col-span-2 lg:col-start-2 lg:row-start-1 lg:flex-row-reverse lg:items-center`}
          >
            <div className="flex-none text-center lg:w-56 lg:text-right">
              <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-white/15">
                <Brain className="h-6 w-6" />
              </div>
              <h3 className="text-xl font-bold leading-relaxed md:text-2xl">
                آزمون آنلاین طراحی‌شده توسط هوش مصنوعی
              </h3>
            </div>
            {/* Screenshot deliberately dominates the card (bigger than the text) */}
            <div className="w-full flex-1 self-center">
              <Image
                src="/landing/exam-builder-dark.png"
                alt="آزمون آنلاین هوش مصنوعی"
                width={583}
                height={304}
                unoptimized
                className="h-auto w-full rounded-xl border border-white/10 shadow-2xl"
              />
            </div>
            <div className="absolute -top-16 -right-10 h-44 w-44 rounded-full bg-white/10 blur-2xl" />
          </motion.div>

          {/* C — Learning stages (orange, half-width on mobile, left) */}
          <motion.div
            dir="rtl"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-50px' }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className={`${cardBase} col-span-1 flex flex-col bg-gradient-to-br from-amber-500 to-orange-600 p-5 md:p-8 lg:col-start-3 lg:row-start-2`}
          >
            <h3 className="mb-4 text-base font-bold sm:text-xl md:text-2xl">
              دسته‌بندی مراحل یادگیری
            </h3>
            <div className="relative mt-auto -mb-5 flex justify-center md:-mb-8">
              <Image
                src="/landing/phone-stages-dark.png"
                alt="دسته‌بندی مراحل یادگیری"
                width={236}
                height={288}
                unoptimized
                className="h-auto w-36 rounded-t-2xl border border-b-0 border-white/10 shadow-2xl sm:w-44"
              />
            </div>
            <div className="absolute -bottom-14 -left-8 h-40 w-40 rounded-full bg-white/10 blur-2xl" />
          </motion.div>

          {/* D — Konkur simulator (green, half-width on mobile, right) */}
          <motion.div
            dir="rtl"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-50px' }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className={`${cardBase} col-span-1 flex flex-col bg-gradient-to-br from-emerald-600 to-teal-700 p-5 md:p-8 lg:col-start-2 lg:row-start-2`}
          >
            <h3 className="mb-4 text-base font-bold sm:text-xl md:text-2xl">
              شبیه‌ساز آزمون کنکور
            </h3>
            <div className="mt-auto">
              <Image
                src="/landing/quiz-sim-dark.png"
                alt="شبیه‌ساز آزمون کنکور"
                width={428}
                height={187}
                unoptimized
                className="h-auto w-full rounded-xl border border-white/10 shadow-2xl"
              />
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
};
