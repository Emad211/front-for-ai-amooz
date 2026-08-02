'use client';

import Image from 'next/image';
import { motion } from 'framer-motion';
import { Settings } from 'lucide-react';

const cardBase = 'relative overflow-hidden rounded-[20px] text-white shadow-xl ring-1 ring-white/10';

export const FeaturesSection = () => {
  return (
    <section id="features" className="landing-section-shell h-[1403px] px-2 pt-10 md:h-auto md:px-8 md:py-20 min-[1820px]:h-[1149px] min-[1820px]:px-8 min-[1820px]:py-10">
      <div className="landing-panel mx-auto h-[1363px] w-full max-w-[1856px] overflow-hidden px-2 pt-10 md:h-auto md:max-w-[1200px] md:px-8 md:pb-10 min-[1820px]:h-[1069px] min-[1820px]:max-w-[1856px] min-[1820px]:px-24 min-[1820px]:pb-0">
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
          <h2 className="landing-display mt-8 h-[45px] text-[32px] font-black leading-[45px] text-foreground min-[1820px]:h-[67px] min-[1820px]:text-[48px] min-[1820px]:leading-[67px]">
            همه‌چیز در یک مکان
          </h2>
          <p className="mx-auto mt-8 min-h-7 max-w-[777px] px-2 text-sm font-medium leading-7 text-muted-foreground sm:text-lg min-[1820px]:h-7 min-[1820px]:px-0 min-[1820px]:text-xl">
            همه چیزی که از یک ابزار یادگیری نیاز دارید؛ یکجا، منظم و هوشمند
          </p>
        </motion.div>

        <div
          dir="ltr"
          className="mx-auto mt-8 grid h-[1108px] w-full max-w-[408px] grid-cols-2 grid-rows-[512px_320px_256px] gap-[10px] md:h-[904px] md:max-w-[960px] md:grid-cols-2 md:grid-rows-[520px_360px] md:gap-6 min-[1820px]:h-[760px] min-[1820px]:max-w-[1664px] min-[1820px]:grid-cols-[minmax(0,458fr)_minmax(0,571fr)_minmax(0,571fr)] min-[1820px]:grid-rows-[336px_304px] min-[1820px]:gap-8 min-[1820px]:py-11"
        >
          <motion.article
            dir="rtl"
            initial={{ opacity: 0, y: 22 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            className={`${cardBase} col-span-2 row-start-1 bg-gradient-to-br from-violet-600 to-purple-700 md:col-span-1 md:col-start-1 md:row-start-1 min-[1820px]:col-span-1 min-[1820px]:col-start-1 min-[1820px]:row-span-2`}
          >
            <div aria-hidden className="absolute -bottom-20 -right-20 h-64 w-64 rounded-full bg-white/10 blur-3xl" />
            <div
              aria-hidden
              className="absolute left-[41.864%] top-[19.5px] h-[527.914px] w-[131.263%] rotate-[39deg] bg-[url('/logo.png')] bg-contain bg-center bg-no-repeat opacity-[.06] min-[1820px]:left-[42.753%] min-[1820px]:top-[99.5px] min-[1820px]:w-[535.555px]"
            />
            <h3 className="relative pt-[62px] text-center text-[32px] font-black leading-8">دستیار هوشمند</h3>
            <Image
              src="/landing/iphone-chat-dark.png"
              alt="دستیار هوشمند AI-Amooz"
              width={243}
              height={578}
              quality={95}
              sizes="243px"
              className="absolute left-1/2 top-[147px] h-[578.25px] w-[242.925px] -translate-x-1/2 object-cover object-top drop-shadow-2xl"
            />
          </motion.article>

          <motion.article
            dir="rtl"
            initial={{ opacity: 0, y: 22 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ delay: 0.06 }}
            className={`${cardBase} col-span-2 row-start-2 bg-gradient-to-br from-rose-600 to-pink-700 md:col-span-1 md:col-start-2 md:row-start-1 min-[1820px]:col-span-2 min-[1820px]:col-start-2 min-[1820px]:row-start-1`}
          >
            <div aria-hidden className="absolute -bottom-24 -left-12 h-[31rem] w-[31rem] rounded-full bg-white/35 blur-[75px]" />
            <h3 className="absolute right-[5.638%] top-12 z-10 w-[89.95%] text-right text-[25px] font-black leading-[1.35] md:right-6 md:w-[calc(100%_-_3rem)] md:text-[28px] min-[1820px]:right-8 min-[1820px]:top-[123.5px] min-[1820px]:w-[404px] min-[1820px]:text-[32px]">
              آزمون آنلاین طراحی‌شده توسط هوش مصنوعی
            </h3>
            <Image
              src="/landing/exam-builder-dark.png"
              alt="سازنده آزمون هوشمند"
              width={583}
              height={376}
              quality={95}
              sizes="(max-width: 767px) 91vw, (max-width: 1279px) 426px, 583px"
              className="absolute left-[5.638%] top-[153.521px] h-auto w-[90.956%] -skew-x-1 rounded-[15px] border border-white/10 object-cover object-top shadow-2xl md:top-[190px] min-[1820px]:left-[22.562px] min-[1820px]:top-8 min-[1820px]:w-[582.562px]"
            />
          </motion.article>

          <motion.article
            dir="rtl"
            initial={{ opacity: 0, y: 22 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ delay: 0.12 }}
            className={`${cardBase} col-start-2 row-start-3 bg-gradient-to-br from-emerald-600 to-teal-700 md:col-start-1 md:row-start-2 min-[1820px]:col-start-2 min-[1820px]:row-start-2`}
          >
            <div aria-hidden className="absolute left-[-86.935%] top-[41px] h-[613.777px] w-[330.093%] select-none text-[38rem] font-black leading-none text-white/10 md:-bottom-80 md:left-auto md:right-[-15rem] md:top-auto md:h-auto md:w-auto md:text-[45rem] min-[1820px]:left-[-41.894%] min-[1820px]:top-[77.5px] min-[1820px]:h-[1202.508px] min-[1820px]:w-[225.337%] min-[1820px]:text-[78rem]">*</div>
            <h3 className="relative px-2 pt-12 text-center text-[18px] font-black leading-8 md:px-8 md:pt-8 md:text-[28px] min-[1820px]:text-[32px]">
              شبیه‌ساز آزمون کنکور
            </h3>
            <Image
              src="/landing/quiz-sim-dark.png"
              alt="شبیه‌ساز آزمون کنکور"
              width={428}
              height={221}
              quality={95}
              sizes="(max-width: 767px) 156vw, (max-width: 1279px) 311px, 428px"
              className="absolute left-[-83.417%] top-[132px] h-auto w-[156.281%] rounded-xl border border-white/10 object-cover object-top shadow-2xl md:left-1/2 md:top-[160px] md:w-[311px] md:-translate-x-1/2 min-[1820px]:left-[72px] min-[1820px]:top-[117px] min-[1820px]:w-[428px] min-[1820px]:translate-x-0"
            />
          </motion.article>

          <motion.article
            dir="rtl"
            initial={{ opacity: 0, y: 22 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ delay: 0.18 }}
            className={`${cardBase} col-start-1 row-start-3 bg-gradient-to-br from-amber-500 to-orange-600 md:col-start-2 md:row-start-2 min-[1820px]:col-start-3 min-[1820px]:row-start-2`}
          >
            <h3 className="relative z-10 px-2 pt-12 text-center text-[18px] font-black leading-8 md:px-8 md:text-[28px] min-[1820px]:absolute min-[1820px]:right-8 min-[1820px]:top-[120.5px] min-[1820px]:w-[304px] min-[1820px]:px-0 min-[1820px]:pt-0 min-[1820px]:text-right min-[1820px]:text-[32px]">
              دسته‌بندی مراحل یادگیری
            </h3>
            <Image
              src="/landing/phone-stages-dark.png"
              alt="مراحل یادگیری"
              width={299}
              height={646}
              quality={95}
              sizes="(max-width: 767px) 75vw, (max-width: 1279px) 180px, 299px"
              className="absolute left-[12.405%] top-[132.875px] h-auto w-[75.188%] object-cover object-top drop-shadow-2xl md:left-8 md:top-[142px] md:w-[180px] min-[1820px]:left-[-64px] min-[1820px]:top-4 min-[1820px]:w-[299.25px]"
            />
          </motion.article>
        </div>
      </div>
    </section>
  );
};
