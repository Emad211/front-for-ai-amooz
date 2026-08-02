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

type ProductImage = {
  src: string;
  alt: string;
  width: number;
  height: number;
  mobileSrc?: string;
  mobileWidth?: number;
  mobileHeight?: number;
};

type TeacherFeature = {
  icon: LucideIcon;
  title: string;
  description: string;
  image: ProductImage;
  objectPosition?: string;
};

const TEACHER_FEATURES: TeacherFeature[] = [
  {
    icon: UsersRound,
    title: 'مدیریت کلاس و دانش‌آموزان',
    description: 'کلاس، فصل‌ها، محتوای منتشرشده و وضعیت دانش‌آموزان را از یک نمای منظم مدیریت و بازبینی کنید.',
    image: TEACHER_PRODUCT_ASSETS.classOverview,
    objectPosition: '50% 12%',
  },
  {
    icon: Sparkles,
    title: 'ساخت آزمون با هوش مصنوعی',
    description: 'فایل حل تست را وارد کنید تا ترنسکریپت و سؤال‌ها استخراج شوند؛ پیش‌نویس را پیش از انتشار خودتان بازبینی کنید.',
    image: TEACHER_PRODUCT_ASSETS.examPrep,
    objectPosition: '50% 8%',
  },
  {
    icon: ClipboardCheck,
    title: 'تصحیح و نمره‌دهی خودکار',
    description: 'پاسخ‌ها را هوش مصنوعی تصحیح می‌کند و برای هر دانش‌آموز بازخورد قابل بازبینی می‌نویسد.',
    image: TEACHER_PRODUCT_ASSETS.exercise,
    objectPosition: '50% 10%',
  },
  {
    icon: BarChart3,
    title: 'داشبورد تحلیل پیشرفت',
    description: 'تعداد کلاس‌ها و دانش‌آموزان، فعالیت‌ها و روند رشد را با شاخص‌ها و نمودارهای روشن زیر نظر بگیرید.',
    image: TEACHER_PRODUCT_ASSETS.analytics,
    objectPosition: '50% 8%',
  },
];

function TeacherScreen({ feature, sizes }: { feature: TeacherFeature; sizes: string }) {
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={feature.title}
        initial={{ opacity: 0, scale: 0.99 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.99 }}
        transition={{ duration: 0.22 }}
        className="absolute inset-0"
      >
        <Image
          src={feature.image.src}
          alt={feature.image.alt}
          fill
          sizes={sizes}
          quality={92}
          className="object-cover"
          style={{ objectPosition: feature.objectPosition ?? '50% 8%' }}
        />
      </motion.div>
    </AnimatePresence>
  );
}

function FeatureIconButton({
  feature,
  active,
  onActivate,
}: {
  feature: TeacherFeature;
  active: boolean;
  onActivate: () => void;
}) {
  const Icon = feature.icon;

  return (
    <button
      type="button"
      aria-label={feature.title}
      aria-pressed={active}
      onClick={onActivate}
      className={`relative flex aspect-square min-w-0 items-center justify-center rounded-xl border transition-[transform,background-color,border-color,box-shadow] duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 ${
        active
          ? '-translate-y-2 border-white/25 bg-white/20 text-white shadow-[0_16px_26px_rgba(3,7,17,.25)] backdrop-blur-xl'
          : 'border-transparent bg-[#030711]/15 text-white/80 hover:bg-[#030711]/20'
      }`}
    >
      <Icon className="h-6 w-6" strokeWidth={1.8} />
      {active && <span aria-hidden className="absolute bottom-2 h-1 w-5 rounded-full bg-white/75" />}
    </button>
  );
}

function CompactLaptop({ feature }: { feature: TeacherFeature }) {
  return (
    <div className="relative aspect-[406/210] w-[calc(100%_-_2px)] max-w-[406px] sm:max-w-[680px]">
      <div className="absolute inset-x-[2%] bottom-[2%] top-[8%] rounded-[22px] bg-black/35 blur-md" />
      <div className="absolute left-[8.5%] right-[8.5%] top-[5.5%] h-[83%] rounded-t-[16px] bg-gradient-to-b from-[#121b29] to-[#050a12] p-[7px] shadow-[0_22px_40px_rgba(3,7,17,.48)]">
        <div className="relative h-full w-full overflow-hidden rounded-[8px] bg-[#030711] ring-1 ring-white/10">
          <TeacherScreen feature={feature} sizes="(max-width: 767px) 74vw, 520px" />
        </div>
      </div>
      <div className="absolute inset-x-0 bottom-0 h-[8%] rounded-b-[16px] bg-gradient-to-b from-[#d7dde6] via-[#aeb7c3] to-[#737e8c] shadow-[0_12px_22px_rgba(3,7,17,.28)]" />
      <div className="absolute bottom-[1.4%] left-1/2 h-[2.5%] w-[24%] -translate-x-1/2 rounded-b-xl bg-[#6f7987]/70" />
      <div className="absolute left-1/2 top-0 z-20 flex -translate-x-1/2 items-center gap-1 rounded-t-md bg-[#030711] px-3 py-1.5 text-[8px] shadow-lg">
        مخصوص دبیران <Sparkles className="h-3 w-3" />
      </div>
    </div>
  );
}

function MobileTeacherShowcase({
  activeIndex,
  setActiveIndex,
}: {
  activeIndex: number;
  setActiveIndex: (index: number) => void;
}) {
  const activeFeature = TEACHER_FEATURES[activeIndex] ?? TEACHER_FEATURES[2]!;

  return (
    <div className="relative flex flex-col gap-14 px-2 py-10 lg:hidden">
      <div className="flex min-h-[189px] flex-col justify-center text-center">
        <h2 className="landing-display text-[32px] font-black leading-[1.35] sm:text-[38px]">
          تدریست رو با هوش مصنوعی متحول کن
        </h2>
        <p className="mx-auto mt-6 max-w-[680px] text-[16px] font-medium leading-7 text-white/90 sm:text-[18px] sm:leading-8">
          همان موتور هوشمندی که کنار دانش‌آموزهاست، ابزارهای حرفه‌ای را هم در اختیار معلم‌ها می‌گذارد؛ از ساخت آزمون و تصحیح خودکار تا تحلیل دقیق پیشرفت کلاس.
        </p>
      </div>

      <div className="flex flex-col items-center gap-8">
        <div dir="ltr" className="grid w-full max-w-[440px] grid-cols-4 gap-2 sm:gap-3">
          {TEACHER_FEATURES.map((feature, index) => (
            <FeatureIconButton
              key={feature.title}
              feature={feature}
              active={index === activeIndex}
              onActivate={() => setActiveIndex(index)}
            />
          ))}
        </div>

        <CompactLaptop feature={activeFeature} />

        <div dir="rtl" className="flex min-h-[92px] w-full max-w-[680px] flex-col items-center justify-center text-center">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={activeFeature.title}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
            >
              <h3 className="text-[24px] font-black leading-8 sm:text-[28px]">{activeFeature.title}</h3>
              <p className="mx-auto mt-4 max-w-[620px] text-[16px] leading-7 text-white/90 sm:text-[17px] sm:leading-8">
                {activeFeature.description}
              </p>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

function DesktopLaptop({ feature }: { feature: TeacherFeature }) {
  return (
    <div className="relative aspect-[1067/600] w-full max-w-[1067px]">
      <div className="absolute -inset-1 rounded-[28px] bg-black/25 blur-md" />
      <div className="absolute inset-x-0 top-0 h-[93.333%] rounded-t-[28px] border-[clamp(12px,0.95vw,18px)] border-[#07101c] bg-[#030711] shadow-[0_30px_70px_rgba(3,7,17,.45)]">
        <div className="relative h-full w-full overflow-hidden rounded-[10px] bg-[#030711]">
          <TeacherScreen feature={feature} sizes="(max-width: 1599px) 55vw, 995px" />
        </div>
      </div>
      <div className="absolute inset-x-0 bottom-0 h-[8.667%] rounded-b-[28px] bg-gradient-to-b from-[#d7dde6] via-[#aeb7c3] to-[#737e8c]" />
      <div className="absolute bottom-[1px] left-1/2 h-[2%] w-[16%] -translate-x-1/2 rounded-b-xl bg-[#66717f]/75" />
      <div className="absolute left-1/2 top-[-5%] z-20 flex -translate-x-1/2 items-center gap-2 rounded-t-[10px] bg-black px-4 py-2 text-[clamp(10px,.75vw,14px)]">
        مخصوص دبیران <Sparkles className="h-[1.4em] w-[1.4em]" />
      </div>
    </div>
  );
}

function DesktopTeacherShowcase({
  activeIndex,
  setActiveIndex,
}: {
  activeIndex: number;
  setActiveIndex: (index: number) => void;
}) {
  const activeFeature = TEACHER_FEATURES[activeIndex] ?? TEACHER_FEATURES[2]!;

  return (
    <div dir="ltr" className="relative hidden min-h-[688px] grid-cols-[52%_48%] items-center lg:grid xl:min-h-[768px]">
      <div className="relative flex h-full items-center overflow-visible">
        <div className="w-[112%] -translate-x-[12%]">
          <DesktopLaptop feature={activeFeature} />
        </div>
      </div>

      <div dir="rtl" className="relative z-10 px-[clamp(28px,5vw,96px)] py-12 text-right">
        <h2 className="landing-display text-[clamp(38px,2.5vw,48px)] font-black leading-[1.4]">
          تدریست رو با هوش مصنوعی متحول کن
        </h2>
        <p className="mt-6 max-w-[777px] text-[clamp(17px,1.05vw,20px)] font-medium leading-[1.65] text-white/90">
          همان موتور هوشمندی که کنار دانش‌آموزهاست، حالا ابزارهای حرفه‌ای را هم در اختیار معلم‌ها می‌گذارد؛ از ساخت آزمون و تصحیح خودکار تا تحلیل دقیق پیشرفت کلاس.
        </p>

        <div className="mt-8 max-w-[777px]">
          {TEACHER_FEATURES.map((feature, index) => {
            const Icon = feature.icon;
            const active = index === activeIndex;

            return (
              <button
                key={feature.title}
                type="button"
                aria-pressed={active}
                onMouseEnter={() => setActiveIndex(index)}
                onFocus={() => setActiveIndex(index)}
                onClick={() => setActiveIndex(index)}
                className={`block w-full overflow-hidden rounded-2xl text-right transition-[height,background-color,border-color,box-shadow] duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 ${
                  active
                    ? 'min-h-[126px] border border-white/20 bg-white/15 p-5 shadow-[0_14px_32px_rgba(3,7,17,.18)] backdrop-blur-xl'
                    : 'min-h-[72px] border border-transparent px-5 py-3 hover:bg-[#030711]/10'
                }`}
              >
                <span className="flex items-center gap-5">
                  <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[#030711]/15">
                    <Icon className="h-6 w-6" />
                  </span>
                  <span className="text-[clamp(18px,1.25vw,24px)] font-bold leading-8">{feature.title}</span>
                </span>
                {active && (
                  <span className="mt-3 block pe-[68px] text-[clamp(14px,.85vw,16px)] leading-7 text-white/90">
                    {feature.description}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export const TeacherCtaSection = () => {
  const [activeIndex, setActiveIndex] = useState(2);

  return (
    <section id="teacher-tools" className="landing-section-shell px-2 pt-10 md:px-8 md:py-10">
      <div className="mx-auto w-full max-w-[424px] sm:max-w-[900px] lg:max-w-[1856px]">
        <div className="relative overflow-hidden rounded-[20px] bg-gradient-to-br from-emerald-600 to-teal-700 text-white shadow-[0_0_4px_hsl(var(--foreground)/.25)]">
          <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="absolute -bottom-48 -left-48 h-[40rem] w-[40rem] rounded-full bg-white/35 blur-[130px]" />
            <div className="absolute -right-40 -top-40 h-[32rem] w-[32rem] rounded-full bg-emerald-200/10 blur-[110px]" />
            <div className="absolute -bottom-[45rem] -right-[25rem] select-none text-[92rem] font-black leading-none text-white/[0.045]">*</div>
          </div>

          <MobileTeacherShowcase activeIndex={activeIndex} setActiveIndex={setActiveIndex} />
          <DesktopTeacherShowcase activeIndex={activeIndex} setActiveIndex={setActiveIndex} />
        </div>
      </div>
    </section>
  );
};
