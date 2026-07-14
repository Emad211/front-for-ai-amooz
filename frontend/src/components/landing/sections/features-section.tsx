'use client';

import Image from 'next/image';
import { motion } from 'framer-motion';
import { Settings } from 'lucide-react';

const cardBase = 'relative overflow-hidden rounded-[20px] text-white shadow-xl ring-1 ring-white/10';

export const FeaturesSection = () => {
  return (
    <section id="features" className="landing-section-shell h-[1403px] px-2 pt-10 lg:h-[1149px] lg:px-8 lg:py-10">
      <div className="landing-panel mx-auto h-[1363px] w-full max-w-[1856px] overflow-hidden px-2 pt-10 lg:h-[1069px] lg:px-24">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center"
        >
          <div className="mx-auto flex h-[38px] w-fit items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-[17px] text-sm font-medium text-primary">
            ویژگی‌ها
            <Settings className="h-4 w-4" />
          </div>
          <h2 className="landing-display mt-8 h-[45px] text-[32px] font-black leading-[45px] text-foreground lg:h-[67px] lg:text-[48px] lg:leading-[67px]">
            همه‌چیز در یک مکان
          </h2>
          <p className="mx-auto mt-8 h-7 max-w-[777px] whitespace-nowrap text-sm font-medium leading-7 text-muted-foreground sm:text-lg lg:text-xl">
            همه چیزی که از یک ابزار یادگیری نیاز دارید؛ یکجا، منظم و هوشمند
          </p>
        </motion.div>

        <div
          dir="ltr"
          className="mx-auto mt-8 grid h-[1108px] w-full max-w-[408px] grid-cols-[199px_199px] grid-rows-[512px_320px_256px] gap-[10px] lg:h-[760px] lg:max-w-[1664px] lg:grid-cols-[458px_571px_571px] lg:grid-rows-[336px_304px] lg:gap-8 lg:py-11"
        >
          <motion.article
            dir="rtl"
            initial={{ opacity: 0, y: 22 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            className={`${cardBase} col-span-2 row-start-1 bg-gradient-to-br from-violet-600 to-purple-700 lg:col-span-1 lg:row-span-2`}
          >
            <div aria-hidden className="absolute -bottom-20 -right-20 h-64 w-64 rounded-full bg-white/10 blur-3xl" />
            <div aria-hidden className="absolute left-[42%] top-[15%] h-72 w-72 rotate-[39deg] bg-[url('/logo.png')] bg-contain bg-center bg-no-repeat opacity-[.06]" />
            <h3 className="relative pt-[62px] text-center text-[32px] font-black leading-8">دستیار هوشمند</h3>
            <Image
              src="/landing/iphone-chat-dark.png"
              alt="دستیار هوشمند AI-Amooz"
              width={243}
              height={578}
              quality={95}
              sizes="243px"
              className="absolute bottom-[-66px] left-1/2 h-[578px] w-[243px] -translate-x-1/2 object-cover object-top drop-shadow-2xl lg:bottom-[-53px]"
            />
          </motion.article>

          <motion.article
            dir="rtl"
            initial={{ opacity: 0, y: 22 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ delay: 0.06 }}
            className={`${cardBase} col-span-2 row-start-2 bg-gradient-to-br from-rose-600 to-pink-700 lg:col-start-2 lg:col-span-2 lg:row-start-1`}
          >
            <div aria-hidden className="absolute -bottom-24 -left-12 h-[31rem] w-[31rem] rounded-full bg-white/35 blur-[75px]" />
            <h3 className="absolute right-6 top-12 z-10 max-w-[367px] text-right text-[25px] font-black leading-[1.35] lg:right-8 lg:top-1/2 lg:w-[404px] lg:-translate-y-1/2 lg:text-[32px]">
              آزمون آنلاین طراحی‌شده توسط هوش مصنوعی
            </h3>
            <Image
              src="/landing/exam-builder-dark.png"
              alt="سازنده آزمون هوشمند"
              width={583}
              height={376}
              quality={95}
              sizes="(max-width: 1023px) 371px, 583px"
              className="absolute -bottom-[74px] left-[23px] h-[239px] w-[371px] -skew-x-1 rounded-[15px] border border-white/10 object-cover object-top shadow-2xl lg:-bottom-10 lg:left-[22px] lg:h-[376px] lg:w-[583px]"
            />
          </motion.article>

          <motion.article
            dir="rtl"
            initial={{ opacity: 0, y: 22 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ delay: 0.12 }}
            className={`${cardBase} col-start-2 row-start-3 bg-gradient-to-br from-emerald-600 to-teal-700 lg:col-start-2 lg:row-start-2`}
          >
            <div aria-hidden className="absolute -bottom-80 -right-60 select-none text-[45rem] font-black leading-none text-white/10">*</div>
            <h3 className="relative px-2 pt-12 text-center text-[18px] font-black leading-8 lg:px-8 lg:pt-8 lg:text-[32px]">
              شبیه‌ساز آزمون کنکور
            </h3>
            <Image
              src="/landing/quiz-sim-dark.png"
              alt="شبیه‌ساز آزمون کنکور"
              width={428}
              height={221}
              quality={95}
              sizes="(max-width: 1023px) 311px, 428px"
              className="absolute bottom-[-36px] left-1/2 h-[160px] w-[311px] -translate-x-1/2 rounded-xl border border-white/10 object-cover object-top shadow-2xl lg:bottom-[-34px] lg:h-[221px] lg:w-[428px]"
            />
          </motion.article>

          <motion.article
            dir="rtl"
            initial={{ opacity: 0, y: 22 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ delay: 0.18 }}
            className={`${cardBase} col-start-1 row-start-3 bg-gradient-to-br from-amber-500 to-orange-600 lg:col-start-3 lg:row-start-2`}
          >
            <h3 className="relative z-10 px-2 pt-12 text-center text-[18px] font-black leading-8 lg:absolute lg:right-8 lg:top-1/2 lg:w-[304px] lg:-translate-y-1/2 lg:px-0 lg:pt-0 lg:text-right lg:text-[32px]">
              دسته‌بندی مراحل یادگیری
            </h3>
            <Image
              src="/landing/phone-stages-dark.png"
              alt="مراحل یادگیری"
              width={299}
              height={646}
              quality={95}
              sizes="(max-width: 1023px) 150px, 299px"
              className="absolute left-[25px] top-[133px] h-[323px] w-[150px] object-cover object-top drop-shadow-2xl lg:left-[-64px] lg:top-4 lg:h-[646px] lg:w-[299px]"
            />
          </motion.article>
        </div>
      </div>
    </section>
  );
};
