'use client';

import Image from 'next/image';
import { Settings } from 'lucide-react';

const cardBase = 'relative overflow-hidden text-white shadow-xl ring-1 ring-white/10';

function SectionHeading() {
  return (
    <div className="text-center">
      <div className="mx-auto flex h-[38px] w-fit items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-[17px] text-sm font-medium text-primary">
        ویژگی‌ها
        <Settings className="h-4 w-4" />
      </div>
      <h2 className="landing-display mt-8 text-[32px] font-black leading-[45px] text-foreground md:text-[clamp(36px,2.5vw,48px)] md:leading-[1.4]">
        همه‌چیز در یک مکان
      </h2>
      <p className="mx-auto mt-8 max-w-[777px] px-2 text-[16px] font-medium leading-7 text-muted-foreground md:px-0 md:text-[clamp(17px,1.05vw,20px)]">
        همه‌چیز برای یک مسیر یادگیری منظم، یکپارچه و هوشمند
      </p>
    </div>
  );
}

function MobileFeatures() {
  return (
    <div dir="ltr" className="mx-auto mt-8 flex w-full max-w-[408px] flex-col gap-[10px] md:hidden">
      <article
        dir="rtl"
        className={`${cardBase} aspect-[408/512] w-full rounded-[20px] bg-gradient-to-br from-violet-600 to-purple-700`}
      >
        <div aria-hidden className="absolute -bottom-20 -right-20 h-64 w-64 rounded-full bg-white/10 blur-3xl" />
        <div
          aria-hidden
          className="absolute left-[41.864%] top-[3.81%] h-[103.11%] w-[131.263%] rotate-[39deg] bg-[url('/logo.png')] bg-contain bg-center bg-no-repeat opacity-[.08]"
        />
        <h3 className="absolute inset-x-0 top-[12.109%] z-10 text-center text-[clamp(26px,7.2vw,32px)] font-black leading-none">
          دستیار هوشمند
        </h3>
        <Image
          src="/landing/iphone-chat-dark.png"
          alt="دستیار هوشمند AI-Amooz"
          width={243}
          height={578}
          quality={92}
          sizes="(max-width: 440px) 60vw, 243px"
          className="absolute left-1/2 top-[28.711%] h-auto w-[59.54%] -translate-x-1/2 object-contain drop-shadow-2xl"
        />
      </article>

      <article
        dir="rtl"
        className={`${cardBase} aspect-[408/320] w-full rounded-[10px] bg-gradient-to-br from-rose-600 to-pink-700`}
      >
        <div aria-hidden className="absolute -bottom-24 -left-12 h-[31rem] w-[31rem] rounded-full bg-white/35 blur-[75px]" />
        <h3 className="absolute inset-x-[5.6%] top-[14.5%] z-10 text-center text-[clamp(20px,5.6vw,24px)] font-black leading-[1.45]">
          آزمون آنلاین طراحی‌شده توسط هوش مصنوعی
        </h3>
        <div className="absolute left-[4.61%] top-[47.975%] h-[74.837%] w-[90.956%] -skew-x-1 overflow-hidden rounded-[12px] border border-white/10 shadow-2xl">
          <div className="absolute left-[-36.11%] top-[-35.11%] h-[143.62%] w-[166.67%]">
            <Image
              src="/landing/exam-builder-dark.png"
              alt="سازنده آزمون هوشمند"
              fill
              quality={92}
              sizes="(max-width: 440px) 150vw, 612px"
              className="object-cover object-top"
            />
          </div>
        </div>
      </article>

      <div className="grid grid-cols-2 gap-[10px]">
        <article
          dir="rtl"
          className={`${cardBase} aspect-[199/256] min-w-0 rounded-[10px] bg-gradient-to-br from-amber-500 to-orange-600`}
        >
          <h3 className="absolute inset-x-[3%] top-[18.75%] z-10 text-center text-[clamp(16px,4.8vw,24px)] font-black leading-[1.4]">
            دسته‌بندی مراحل یادگیری
          </h3>
          <Image
            src="/landing/phone-stages-dark.png"
            alt="مراحل یادگیری"
            width={150}
            height={323}
            quality={92}
            sizes="(max-width: 440px) 38vw, 150px"
            className="absolute left-[12.405%] top-[51.9%] h-auto w-[75.188%] object-contain object-top drop-shadow-2xl"
          />
        </article>

        <article
          dir="rtl"
          className={`${cardBase} aspect-[199/256] min-w-0 rounded-[10px] bg-gradient-to-br from-emerald-600 to-teal-700`}
        >
          <div aria-hidden className="absolute -bottom-[120%] -right-[105%] select-none text-[36rem] font-black leading-none text-white/10">*</div>
          <h3 className="absolute inset-x-[3%] top-[18.75%] z-10 text-center text-[clamp(16px,4.8vw,24px)] font-black leading-[1.4]">
            شبیه‌ساز آزمون کنکور
          </h3>
          <div className="absolute left-[-83.417%] top-[51.563%] h-[62.5%] w-[156.281%] overflow-hidden rounded-[16px] border border-white/10 shadow-2xl">
            <Image
              src="/landing/quiz-sim-dark.png"
              alt="شبیه‌ساز آزمون کنکور"
              fill
              quality={92}
              sizes="(max-width: 440px) 71vw, 311px"
              className="object-cover object-top"
            />
          </div>
        </article>
      </div>
    </div>
  );
}

function FluidDesktopFeatures() {
  return (
    <div dir="ltr" className="relative mx-auto mt-8 hidden aspect-[1664/760] w-full max-w-[1664px] md:block">
      <div className="absolute inset-x-0 top-[5.789%] h-[88.421%]">
        <article
          dir="rtl"
          className={`${cardBase} absolute left-0 top-0 h-full w-[27.524%] rounded-[20px] bg-gradient-to-br from-violet-600 to-purple-700`}
        >
          <div aria-hidden className="absolute -bottom-20 -right-20 h-64 w-64 rounded-full bg-white/10 blur-3xl" />
          <div
            aria-hidden
            className="absolute left-[42.753%] top-[14.807%] h-[78.559%] w-[116.933%] rotate-[39deg] bg-[url('/logo.png')] bg-contain bg-center bg-no-repeat opacity-[.08]"
          />
          <h3 className="absolute inset-x-0 top-[9.226%] z-10 text-center text-[clamp(18px,1.667vw,32px)] font-black leading-none">
            دستیار هوشمند
          </h3>
          <Image
            src="/landing/iphone-chat-dark.png"
            alt="دستیار هوشمند AI-Amooz"
            width={243}
            height={578}
            quality={92}
            sizes="(max-width: 1819px) 15vw, 243px"
            className="absolute left-1/2 top-[21.875%] h-auto w-[53.04%] -translate-x-1/2 object-contain drop-shadow-2xl"
          />
        </article>

        <article
          dir="rtl"
          className={`${cardBase} absolute left-[29.447%] top-0 h-1/2 w-[70.553%] rounded-[20px] bg-gradient-to-br from-rose-600 to-pink-700`}
        >
          <div aria-hidden className="absolute -bottom-24 -left-12 h-[31rem] w-[31rem] rounded-full bg-white/35 blur-[75px]" />
          <h3 className="absolute right-[2.726%] top-[36.756%] z-10 w-[34.413%] text-right text-[clamp(18px,1.667vw,32px)] font-black leading-[1.4]">
            آزمون آنلاین طراحی‌شده توسط هوش مصنوعی
          </h3>
          <div className="absolute left-[1.922%] top-[9.524%] h-[111.888%] w-[49.622%] overflow-hidden rounded-[15px] border border-white/10 shadow-2xl">
            <Image
              src="/landing/exam-builder-dark.png"
              alt="سازنده آزمون هوشمند"
              fill
              quality={92}
              sizes="(max-width: 1819px) 35vw, 583px"
              className="object-cover object-top"
            />
          </div>
        </article>

        <article
          dir="rtl"
          className={`${cardBase} absolute left-[29.447%] top-[54.762%] h-[45.238%] w-[34.315%] rounded-[20px] bg-gradient-to-br from-emerald-600 to-teal-700`}
        >
          <div aria-hidden className="absolute -bottom-[160%] -right-[90%] select-none text-[45rem] font-black leading-none text-white/10">*</div>
          <h3 className="absolute inset-x-[8%] top-[10.526%] z-10 text-center text-[clamp(16px,1.667vw,32px)] font-black leading-[1.3]">
            شبیه‌ساز آزمون کنکور
          </h3>
          <div className="absolute left-[12.61%] top-[38.487%] h-[72.697%] w-[74.956%] overflow-hidden rounded-[12px] border border-white/10 shadow-2xl">
            <Image
              src="/landing/quiz-sim-dark.png"
              alt="شبیه‌ساز آزمون کنکور"
              fill
              quality={92}
              sizes="(max-width: 1819px) 26vw, 428px"
              className="object-cover object-top"
            />
          </div>
        </article>

        <article
          dir="rtl"
          className={`${cardBase} absolute left-[65.685%] top-[54.762%] h-[45.238%] w-[34.315%] rounded-[20px] bg-gradient-to-br from-amber-500 to-orange-600`}
        >
          <h3 className="absolute left-[41.156%] top-[39.638%] z-10 w-[53.24%] text-right text-[clamp(16px,1.667vw,32px)] font-black leading-[1.3]">
            دسته‌بندی مراحل یادگیری
          </h3>
          <Image
            src="/landing/phone-stages-dark.png"
            alt="مراحل یادگیری"
            width={299}
            height={646}
            quality={92}
            sizes="(max-width: 1819px) 18vw, 299px"
            className="absolute left-[-11.208%] top-[5.263%] h-auto w-[52.408%] object-contain object-top drop-shadow-2xl"
          />
        </article>
      </div>
    </div>
  );
}

export const FeaturesSection = () => {
  return (
    <section id="features" className="landing-section-shell px-2 pt-10 md:px-8 md:py-10">
      <div className="landing-panel mx-auto w-full max-w-[424px] overflow-hidden px-2 pb-2 pt-10 md:max-w-[1856px] md:px-[clamp(32px,5vw,96px)] md:pb-10">
        <SectionHeading />
        <MobileFeatures />
        <FluidDesktopFeatures />
      </div>
    </section>
  );
};
