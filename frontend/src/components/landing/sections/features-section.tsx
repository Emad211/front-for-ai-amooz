'use client';

import Image from 'next/image';
import { motion } from 'framer-motion';
import { Settings } from 'lucide-react';

const cardBase = 'relative overflow-hidden rounded-[20px] text-white shadow-xl ring-1 ring-white/10';

function SectionHeading() {
  return (
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
      <h2 className="landing-display mt-8 text-[32px] font-black leading-[45px] text-foreground min-[1820px]:text-[48px] min-[1820px]:leading-[67px]">
        همه‌چیز در یک مکان
      </h2>
      <p className="mx-auto mt-8 max-w-[777px] px-2 text-[15px] font-medium leading-7 text-muted-foreground sm:text-lg min-[1820px]:px-0 min-[1820px]:text-xl">
        همه‌چیز برای یک مسیر یادگیری منظم، یکپارچه و هوشمند
      </p>
    </motion.div>
  );
}

function MobileFeatures() {
  return (
    <div dir="ltr" className="mx-auto mt-8 flex w-full max-w-[408px] flex-col gap-[10px] md:hidden">
      <motion.article
        dir="rtl"
        initial={{ opacity: 0, y: 22 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        className={`${cardBase} aspect-[408/512] w-full bg-gradient-to-br from-violet-600 to-purple-700`}
      >
        <div aria-hidden className="absolute -bottom-20 -right-20 h-64 w-64 rounded-full bg-white/10 blur-3xl" />
        <div
          aria-hidden
          className="absolute left-[41.864%] top-[3.81%] h-[103.11%] w-[131.263%] rotate-[39deg] bg-[url('/logo.png')] bg-contain bg-center bg-no-repeat opacity-[.06]"
        />
        <h3 className="absolute inset-x-0 top-[12.109%] z-10 text-center text-[clamp(26px,7.2vw,32px)] font-black leading-none">
          دستیار هوشمند
        </h3>
        <Image
          src="/landing/iphone-chat-dark.png"
          alt="دستیار هوشمند AI-Amooz"
          width={243}
          height={578}
          quality={90}
          sizes="(max-width: 440px) 60vw, 243px"
          className="absolute left-1/2 top-[28.711%] h-auto w-[59.54%] -translate-x-1/2 object-contain drop-shadow-2xl"
        />
      </motion.article>

      <motion.article
        dir="rtl"
        initial={{ opacity: 0, y: 22 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ delay: 0.06 }}
        className={`${cardBase} aspect-[408/320] w-full rounded-[10px] bg-gradient-to-br from-rose-600 to-pink-700`}
      >
        <div aria-hidden className="absolute -bottom-24 -left-12 h-[31rem] w-[31rem] rounded-full bg-white/35 blur-[75px]" />
        <h3 className="absolute inset-x-[5.6%] top-[14.5%] z-10 text-center text-[clamp(20px,5.6vw,24px)] font-black leading-[1.45]">
          آزمون آنلاین طراحی‌شده توسط هوش مصنوعی
        </h3>
        <div className="absolute left-[4.61%] top-[47.975%] h-[74.837%] w-[90.956%] overflow-hidden rounded-[12px] border border-white/10 shadow-2xl">
          <Image
            src="/landing/exam-builder-dark.png"
            alt="سازنده آزمون هوشمند"
            fill
            quality={90}
            sizes="(max-width: 440px) 91vw, 371px"
            className="object-cover object-top"
          />
        </div>
      </motion.article>

      <div className="grid grid-cols-2 gap-[10px]">
        <motion.article
          dir="rtl"
          initial={{ opacity: 0, y: 22 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ delay: 0.12 }}
          className={`${cardBase} aspect-[199/256] rounded-[10px] bg-gradient-to-br from-amber-500 to-orange-600`}
        >
          <h3 className="absolute inset-x-[3%] top-[18.75%] z-10 text-center text-[clamp(16px,4.8vw,24px)] font-black leading-[1.4]">
            دسته‌بندی مراحل یادگیری
          </h3>
          <Image
            src="/landing/phone-stages-dark.png"
            alt="مراحل یادگیری"
            width={150}
            height={323}
            quality={90}
            sizes="(max-width: 440px) 38vw, 150px"
            className="absolute left-[12.405%] top-[51.9%] h-auto w-[75.188%] object-contain object-top drop-shadow-2xl"
          />
        </motion.article>

        <motion.article
          dir="rtl"
          initial={{ opacity: 0, y: 22 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ delay: 0.18 }}
          className={`${cardBase} aspect-[199/256] rounded-[10px] bg-gradient-to-br from-emerald-600 to-teal-700`}
        >
          <div aria-hidden className="absolute -bottom-[120%] -right-[105%] select-none text-[36rem] font-black leading-none text-white/10">*</div>
          <h3 className="absolute inset-x-[3%] top-[18.75%] z-10 text-center text-[clamp(16px,4.8vw,24px)] font-black leading-[1.4]">
            شبیه‌ساز آزمون کنکور
          </h3>
          <div className="absolute inset-x-0 bottom-[-2%] top-[51.5%] overflow-hidden">
            <Image
              src="/landing/quiz-sim-dark.png"
              alt="شبیه‌ساز آزمون کنکور"
              fill
              quality={90}
              sizes="(max-width: 440px) 45vw, 199px"
              className="object-cover object-top"
            />
          </div>
        </motion.article>
      </div>
    </div>
  );
}

function ResponsiveFeatures() {
  return (
    <div
      dir="ltr"
      className="mx-auto mt-10 hidden w-full max-w-[960px] grid-cols-2 grid-rows-[520px_360px] gap-6 md:grid min-[1820px]:hidden"
    >
      <motion.article
        dir="rtl"
        initial={{ opacity: 0, y: 22 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        className={`${cardBase} bg-gradient-to-br from-violet-600 to-purple-700`}
      >
        <div aria-hidden className="absolute -bottom-20 -right-20 h-64 w-64 rounded-full bg-white/10 blur-3xl" />
        <h3 className="relative pt-12 text-center text-[30px] font-black">دستیار هوشمند</h3>
        <Image
          src="/landing/iphone-chat-dark.png"
          alt="دستیار هوشمند AI-Amooz"
          width={243}
          height={578}
          quality={90}
          sizes="243px"
          className="absolute bottom-[-70px] left-1/2 h-[430px] w-auto -translate-x-1/2 object-contain drop-shadow-2xl"
        />
      </motion.article>

      <motion.article
        dir="rtl"
        initial={{ opacity: 0, y: 22 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ delay: 0.06 }}
        className={`${cardBase} bg-gradient-to-br from-rose-600 to-pink-700`}
      >
        <div aria-hidden className="absolute -bottom-24 -left-12 h-[31rem] w-[31rem] rounded-full bg-white/35 blur-[75px]" />
        <h3 className="absolute inset-x-8 top-10 z-10 text-center text-[28px] font-black leading-[1.45]">
          آزمون آنلاین طراحی‌شده توسط هوش مصنوعی
        </h3>
        <div className="absolute inset-x-6 bottom-[-28px] h-[315px] overflow-hidden rounded-2xl border border-white/10 shadow-2xl">
          <Image src="/landing/exam-builder-dark.png" alt="سازنده آزمون هوشمند" fill quality={90} sizes="430px" className="object-cover object-top" />
        </div>
      </motion.article>

      <motion.article
        dir="rtl"
        initial={{ opacity: 0, y: 22 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ delay: 0.12 }}
        className={`${cardBase} bg-gradient-to-br from-emerald-600 to-teal-700`}
      >
        <h3 className="relative px-8 pt-8 text-center text-[28px] font-black">شبیه‌ساز آزمون کنکور</h3>
        <div className="absolute inset-x-8 bottom-[-20px] h-[245px] overflow-hidden rounded-xl border border-white/10 shadow-2xl">
          <Image src="/landing/quiz-sim-dark.png" alt="شبیه‌ساز آزمون کنکور" fill quality={90} sizes="400px" className="object-cover object-top" />
        </div>
      </motion.article>

      <motion.article
        dir="rtl"
        initial={{ opacity: 0, y: 22 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ delay: 0.18 }}
        className={`${cardBase} bg-gradient-to-br from-amber-500 to-orange-600`}
      >
        <h3 className="relative z-10 px-8 pt-8 text-center text-[28px] font-black">دسته‌بندی مراحل یادگیری</h3>
        <Image
          src="/landing/phone-stages-dark.png"
          alt="مراحل یادگیری"
          width={180}
          height={390}
          quality={90}
          sizes="180px"
          className="absolute bottom-[-110px] left-1/2 h-[390px] w-auto -translate-x-1/2 object-contain drop-shadow-2xl"
        />
      </motion.article>
    </div>
  );
}

function DesktopFeatures() {
  return (
    <div
      dir="ltr"
      className="mx-auto mt-8 hidden h-[760px] w-full max-w-[1664px] grid-cols-[458px_571px_571px] grid-rows-[336px_304px] gap-8 py-11 min-[1820px]:grid"
    >
      <motion.article
        dir="rtl"
        initial={{ opacity: 0, y: 22 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        className={`${cardBase} col-span-1 row-span-2 bg-gradient-to-br from-violet-600 to-purple-700`}
      >
        <div aria-hidden className="absolute -bottom-20 -right-20 h-64 w-64 rounded-full bg-white/10 blur-3xl" />
        <div aria-hidden className="absolute left-[42.753%] top-[99.5px] h-[527.914px] w-[535.555px] rotate-[39deg] bg-[url('/logo.png')] bg-contain bg-center bg-no-repeat opacity-[.06]" />
        <h3 className="relative pt-[62px] text-center text-[32px] font-black leading-8">دستیار هوشمند</h3>
        <Image
          src="/landing/iphone-chat-dark.png"
          alt="دستیار هوشمند AI-Amooz"
          width={243}
          height={578}
          quality={90}
          sizes="243px"
          className="absolute bottom-[-53px] left-1/2 h-[578px] w-[243px] -translate-x-1/2 object-contain drop-shadow-2xl"
        />
      </motion.article>

      <motion.article
        dir="rtl"
        initial={{ opacity: 0, y: 22 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ delay: 0.06 }}
        className={`${cardBase} col-span-2 col-start-2 row-start-1 bg-gradient-to-br from-rose-600 to-pink-700`}
      >
        <div aria-hidden className="absolute -bottom-24 -left-12 h-[31rem] w-[31rem] rounded-full bg-white/35 blur-[75px]" />
        <h3 className="absolute right-8 top-[123.5px] z-10 w-[404px] text-right text-[32px] font-black leading-[1.4]">
          آزمون آنلاین طراحی‌شده توسط هوش مصنوعی
        </h3>
        <div className="absolute left-[22.562px] top-8 h-[376px] w-[582.562px] overflow-hidden rounded-[15px] border border-white/10 shadow-2xl">
          <Image src="/landing/exam-builder-dark.png" alt="سازنده آزمون هوشمند" fill quality={90} sizes="583px" className="object-cover object-top" />
        </div>
      </motion.article>

      <motion.article
        dir="rtl"
        initial={{ opacity: 0, y: 22 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ delay: 0.12 }}
        className={`${cardBase} col-start-2 row-start-2 bg-gradient-to-br from-emerald-600 to-teal-700`}
      >
        <div aria-hidden className="absolute -bottom-80 -right-60 select-none text-[45rem] font-black leading-none text-white/10">*</div>
        <h3 className="relative px-8 pt-8 text-center text-[32px] font-black">شبیه‌ساز آزمون کنکور</h3>
        <div className="absolute bottom-[-34px] left-[72px] h-[221px] w-[428px] overflow-hidden rounded-xl border border-white/10 shadow-2xl">
          <Image src="/landing/quiz-sim-dark.png" alt="شبیه‌ساز آزمون کنکور" fill quality={90} sizes="428px" className="object-cover object-top" />
        </div>
      </motion.article>

      <motion.article
        dir="rtl"
        initial={{ opacity: 0, y: 22 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ delay: 0.18 }}
        className={`${cardBase} col-start-3 row-start-2 bg-gradient-to-br from-amber-500 to-orange-600`}
      >
        <h3 className="absolute right-8 top-[120.5px] z-10 w-[304px] text-right text-[32px] font-black leading-10">
          دسته‌بندی مراحل یادگیری
        </h3>
        <Image
          src="/landing/phone-stages-dark.png"
          alt="مراحل یادگیری"
          width={299}
          height={646}
          quality={90}
          sizes="299px"
          className="absolute left-[-64px] top-4 h-[646px] w-[299px] object-contain object-top drop-shadow-2xl"
        />
      </motion.article>
    </div>
  );
}

export const FeaturesSection = () => {
  return (
    <section id="features" className="landing-section-shell px-2 pt-10 md:px-8 md:py-20 min-[1820px]:h-[1149px] min-[1820px]:py-10">
      <div className="landing-panel mx-auto w-full max-w-[424px] overflow-hidden px-2 pb-2 pt-10 md:max-w-[1200px] md:px-8 md:pb-10 min-[1820px]:h-[1069px] min-[1820px]:max-w-[1856px] min-[1820px]:px-24 min-[1820px]:pb-0">
        <SectionHeading />
        <MobileFeatures />
        <ResponsiveFeatures />
        <DesktopFeatures />
      </div>
    </section>
  );
};
