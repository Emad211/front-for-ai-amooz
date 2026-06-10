'use client';

import Image from 'next/image';
import { motion } from 'framer-motion';
import { Bot, Brain, MonitorPlay, Layers, Settings } from 'lucide-react';

/** Lightweight skeleton "dashboard" panel shown inside colored bento cards. */
const MockPanel = ({ className = '', rows = 3 }: { className?: string; rows?: number }) => (
  <div className={`rounded-xl border border-white/10 bg-black/25 p-3 backdrop-blur-sm ${className}`}>
    <div className="mb-3 flex items-center gap-1.5">
      <span className="h-2 w-2 rounded-full bg-white/40" />
      <span className="h-2 w-2 rounded-full bg-white/25" />
      <span className="h-2 w-2 rounded-full bg-white/25" />
    </div>
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-2.5 rounded bg-white/15"
          style={{ width: `${85 - i * 18}%` }}
        />
      ))}
    </div>
  </div>
);

const cardBase =
  'group relative overflow-hidden rounded-3xl border border-white/10 p-6 md:p-8 text-white shadow-xl transition-all duration-500 hover:shadow-2xl';

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
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary">
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
          className="mx-auto grid max-w-6xl grid-cols-1 gap-5 lg:grid-cols-3 lg:grid-rows-2"
        >
          {/* A — Smart assistant (purple, tall) */}
          <motion.div
            dir="rtl"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-50px' }}
            transition={{ duration: 0.5 }}
            className={`${cardBase} bg-gradient-to-br from-violet-600 to-purple-700 lg:col-start-1 lg:row-start-1 lg:row-span-2`}
          >
            <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-white/15">
              <Bot className="h-6 w-6" />
            </div>
            <h3 className="mb-2 text-xl font-bold md:text-2xl">دستیار هوشمند</h3>
            <p className="mb-6 text-sm leading-7 text-white/75">
              هر لحظه که سوالی داشتی، کنارت است؛ رفع اشکال، توضیح گام‌به‌گام و راه‌حل‌های جایگزین.
            </p>
            <div className="relative mx-auto mt-auto w-32 sm:w-36">
              <div className="aspect-[9/19] overflow-hidden rounded-[1.5rem] border-4 border-black/40 bg-black/40 shadow-2xl">
                <Image
                  src="/homee.png"
                  alt="دستیار هوشمند AI-Amooz"
                  width={180}
                  height={380}
                  className="h-full w-full object-cover"
                />
              </div>
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
            className={`${cardBase} flex flex-col items-center gap-6 bg-gradient-to-br from-rose-500 to-pink-600 sm:flex-row-reverse lg:col-start-2 lg:col-span-2 lg:row-start-1`}
          >
            <div className="flex-1 text-center sm:text-right">
              <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-white/15">
                <Brain className="h-6 w-6" />
              </div>
              <h3 className="text-xl font-bold leading-relaxed md:text-2xl">
                آزمون آنلاین طراحی‌شده توسط هوش مصنوعی
              </h3>
            </div>
            <MockPanel className="w-full max-w-xs flex-1" rows={4} />
            <div className="absolute -top-16 -right-10 h-44 w-44 rounded-full bg-white/10 blur-2xl" />
          </motion.div>

          {/* C — Konkur simulator (emerald-dark) */}
          <motion.div
            dir="rtl"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-50px' }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className={`${cardBase} bg-gradient-to-br from-emerald-800 to-teal-900 lg:col-start-2 lg:row-start-2`}
          >
            <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10">
              <MonitorPlay className="h-6 w-6 text-emerald-300" />
            </div>
            <h3 className="mb-4 text-xl font-bold md:text-2xl">شبیه‌ساز آزمون کنکور</h3>
            <MockPanel rows={3} />
          </motion.div>

          {/* D — Learning stages (orange) */}
          <motion.div
            dir="rtl"
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-50px' }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className={`${cardBase} flex flex-col items-center gap-5 bg-gradient-to-br from-orange-500 to-amber-600 sm:flex-row-reverse lg:col-start-3 lg:row-start-2`}
          >
            <div className="flex-1 text-center sm:text-right">
              <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-white/15">
                <Layers className="h-6 w-6" />
              </div>
              <h3 className="text-xl font-bold md:text-2xl">دسته‌بندی مراحل یادگیری</h3>
            </div>
            <MockPanel className="w-full max-w-[10rem] flex-1" rows={3} />
            <div className="absolute -bottom-14 -left-8 h-40 w-40 rounded-full bg-white/10 blur-2xl" />
          </motion.div>
        </div>
      </div>
    </section>
  );
};
