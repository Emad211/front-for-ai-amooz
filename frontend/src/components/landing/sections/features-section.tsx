'use client';

import Image from 'next/image';
import { motion } from 'framer-motion';
import { Settings } from 'lucide-react';

const baseCard =
  'relative overflow-hidden rounded-[1.25rem] text-white shadow-xl ring-1 ring-white/10';

export const FeaturesSection = () => {
  return (
    <section id="features" className="landing-section-shell px-2 py-10 sm:px-4 lg:px-8">
      <div className="landing-panel mx-auto w-full max-w-[1856px] overflow-hidden px-4 py-10 sm:px-8 lg:px-24">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center"
        >
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-[17px] py-[9px] text-sm font-medium text-primary">
            ویژگی‌ها
            <Settings className="h-4 w-4" />
          </div>
          <h2 className="landing-display mt-8 text-3xl font-black text-foreground sm:text-4xl lg:text-5xl">
            همه چیز در یک مکان
          </h2>
          <p className="mx-auto mt-6 max-w-3xl text-base font-medium text-muted-foreground sm:text-lg lg:text-xl">
            همه چیزی که از یک ابزار یادگیری نیاز دارید؛ یکجا، منظم و هوشمند
          </p>
        </motion.div>

        <div
          dir="ltr"
          className="mt-12 grid min-h-[43rem] grid-cols-2 gap-3 sm:gap-5 lg:grid-cols-[458px_1fr_1fr] lg:grid-rows-[336px_304px] lg:gap-8"
        >
          <motion.article
            dir="rtl"
            initial={{ opacity: 0, y: 26 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            className={`${baseCard} col-span-2 min-h-[32rem] bg-gradient-to-br from-violet-600 to-purple-700 lg:col-span-1 lg:row-span-2 lg:min-h-0`}
          >
            <div aria-hidden className="absolute -bottom-24 -right-24 h-72 w-72 rounded-full bg-white/10 blur-3xl" />
            <h3 className="relative pt-14 text-center text-3xl font-black">دستیار هوشمند</h3>
            <div className="absolute inset-x-0 bottom-0 flex justify-center">
              <Image
                src="/landing/iphone-chat-dark.png"
                alt="دستیار هوشمند AI-Amooz"
                width={243}
                height={578}
                className="h-auto w-[15rem] max-w-[66%] drop-shadow-2xl lg:w-[15.2rem]"
              />
            </div>
          </motion.article>

          <motion.article
            dir="rtl"
            initial={{ opacity: 0, y: 26 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ delay: 0.08 }}
            className={`${baseCard} col-span-2 min-h-[20rem] bg-gradient-to-br from-rose-600 to-pink-700 lg:col-span-2 lg:min-h-0`}
          >
            <div aria-hidden className="absolute -bottom-32 left-8 h-[31rem] w-[31rem] rounded-full bg-white/35 blur-[75px]" />
            <h3 className="absolute right-6 top-12 z-10 max-w-[24rem] text-right text-2xl font-black leading-[1.4] sm:right-10 sm:text-3xl lg:right-8 lg:top-1/2 lg:-translate-y-1/2 lg:text-4xl">
              آزمون آنلاین طراحی‌شده توسط هوش مصنوعی
            </h3>
            <Image
              src="/landing/exam-builder-dark.png"
              alt="سازنده آزمون هوشمند"
              width={583}
              height={376}
              unoptimized
              className="absolute -bottom-6 -left-10 h-auto w-[72%] max-w-[37rem] -skew-x-1 rounded-2xl border border-white/10 object-cover shadow-2xl sm:-left-4 lg:left-5 lg:top-8 lg:w-[50%]"
            />
          </motion.article>

          <motion.article
            dir="rtl"
            initial={{ opacity: 0, y: 26 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ delay: 0.14 }}
            className={`${baseCard} col-span-1 min-h-64 bg-gradient-to-br from-emerald-600 to-teal-700 lg:min-h-0`}
          >
            <div aria-hidden className="absolute -bottom-80 -right-60 select-none text-[45rem] font-black leading-none text-white/10">*</div>
            <h3 className="relative px-3 pt-10 text-center text-lg font-black leading-8 sm:text-2xl lg:text-3xl">
              شبیه‌ساز آزمون کنکور
            </h3>
            <Image
              src="/landing/quiz-sim-dark.png"
              alt="شبیه‌ساز آزمون کنکور"
              width={428}
              height={221}
              unoptimized
              className="absolute -bottom-5 left-1/2 h-auto w-[82%] -translate-x-1/2 rounded-xl border border-white/10 shadow-2xl"
            />
          </motion.article>

          <motion.article
            dir="rtl"
            initial={{ opacity: 0, y: 26 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ delay: 0.2 }}
            className={`${baseCard} col-span-1 min-h-64 bg-gradient-to-br from-amber-500 to-orange-600 lg:min-h-0`}
          >
            <h3 className="relative z-10 px-3 pt-10 text-center text-lg font-black leading-8 sm:text-2xl lg:absolute lg:right-7 lg:top-1/2 lg:max-w-[19rem] lg:-translate-y-1/2 lg:text-right lg:text-3xl">
              دسته‌بندی مراحل یادگیری
            </h3>
            <Image
              src="/landing/phone-stages-dark.png"
              alt="مراحل یادگیری"
              width={299}
              height={646}
              unoptimized
              className="absolute -bottom-36 -left-8 h-auto w-[55%] max-w-[15rem] drop-shadow-2xl sm:-bottom-44 lg:-bottom-80 lg:-left-16 lg:w-[52%]"
            />
          </motion.article>
        </div>
      </div>
    </section>
  );
};
