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
};

const TEACHER_FEATURES: TeacherFeature[] = [
  {
    icon: UsersRound,
    title: 'مدیریت کلاس و دانش‌آموزان',
    description: 'کلاس، فصل‌ها، محتوای منتشرشده و وضعیت دانش‌آموزان را از یک نمای منظم مدیریت و بازبینی کنید.',
    image: TEACHER_PRODUCT_ASSETS.classOverview,
  },
  {
    icon: Sparkles,
    title: 'ساخت آزمون با هوش مصنوعی',
    description: 'فایل حل تست را وارد کنید تا ترنسکریپت و سؤال‌ها استخراج شوند؛ پیش‌نویس را پیش از انتشار خودتان بازبینی کنید.',
    image: TEACHER_PRODUCT_ASSETS.examPrep,
  },
  {
    icon: ClipboardCheck,
    title: 'تصحیح و نمره‌دهی خودکار',
    description: 'پاسخ‌ها را هوش مصنوعی تصحیح می‌کند و برای هر دانش‌آموز بازخورد قابل بازبینی می‌نویسد.',
    image: TEACHER_PRODUCT_ASSETS.exercise,
  },
  {
    icon: BarChart3,
    title: 'داشبورد تحلیل پیشرفت',
    description: 'تعداد کلاس‌ها و دانش‌آموزان، فعالیت‌ها و روند رشد را با شاخص‌ها و نمودارهای روشن زیر نظر بگیرید.',
    image: TEACHER_PRODUCT_ASSETS.analytics,
  },
];

function TeacherScreen({
  feature,
  mobile = false,
  contain = false,
}: {
  feature: TeacherFeature;
  mobile?: boolean;
  contain?: boolean;
}) {
  const source = mobile && feature.image.mobileSrc ? feature.image.mobileSrc : feature.image.src;

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={`${feature.title}-${mobile ? 'mobile' : 'desktop'}`}
        initial={{ opacity: 0, scale: 0.985 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.985 }}
        transition={{ duration: 0.25 }}
        className="absolute inset-0"
      >
        <Image
          src={source}
          alt={feature.image.alt}
          fill
          sizes={mobile ? '(max-width: 440px) 88vw, 390px' : '995px'}
          quality={90}
          className={contain ? 'object-contain object-top' : 'object-cover object-top'}
        />
      </motion.div>
    </AnimatePresence>
  );
}

function FeatureIconButton({
  feature,
  active,
  onActivate,
  compact = false,
}: {
  feature: TeacherFeature;
  active: boolean;
  onActivate: () => void;
  compact?: boolean;
}) {
  const Icon = feature.icon;

  return (
    <button
      type="button"
      aria-label={feature.title}
      aria-pressed={active}
      onClick={onActivate}
      className={`relative flex items-center justify-center rounded-2xl border transition-all duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 ${
        compact ? 'h-20' : 'h-[88px]'
      } ${
        active
          ? '-translate-y-1 border-white/25 bg-white/20 text-white shadow-[0_16px_26px_rgba(3,7,17,.25)] backdrop-blur-xl'
          : 'border-transparent bg-[#030711]/15 text-white/75 hover:bg-[#030711]/20'
      }`}
    >
      <Icon className="h-6 w-6" />
      {active && <span aria-hidden className="absolute bottom-2 h-1 w-5 rounded-full bg-white/70" />}
    </button>
  );
}

export const TeacherCtaSection = () => {
  const [activeIndex, setActiveIndex] = useState(2);
  const activeFeature = TEACHER_FEATURES[activeIndex] ?? TEACHER_FEATURES[2]!;

  return (
    <section id="teacher-tools" className="landing-section-shell px-2 pt-10 md:h-[1060px] md:px-8 md:py-10 min-[1820px]:h-[848px]">
      <div className="mx-auto w-full max-w-[424px] md:h-[980px] md:max-w-[1200px] min-[1820px]:h-[768px] min-[1820px]:max-w-[1856px]">
        <div className="relative overflow-hidden rounded-[20px] bg-gradient-to-br from-emerald-600 to-teal-700 text-white shadow-[0_0_4px_hsl(var(--foreground)/.25)] md:h-full">
          <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="absolute -bottom-48 -left-48 h-[40rem] w-[40rem] rounded-full bg-white/35 blur-[130px]" />
            <div className="absolute -right-40 -top-40 h-[32rem] w-[32rem] rounded-full bg-emerald-200/10 blur-[110px]" />
            <div className="absolute -bottom-[45rem] -right-[25rem] select-none text-[92rem] font-black leading-none text-white/[0.045]">*</div>
          </div>

          <div className="relative flex min-h-[790px] flex-col px-4 py-10 md:hidden">
            <div className="text-center">
              <h2 className="landing-display text-[34px] font-black leading-[1.28] sm:text-[36px]">
                تدریست رو با هوش مصنوعی متحول کن
              </h2>
              <p className="mx-auto mt-5 max-w-[390px] text-[15px] font-medium leading-[25px] text-white/90 sm:text-[16px] sm:leading-7">
                همان موتور هوشمندی که کنار دانش‌آموزهاست، ابزارهای حرفه‌ای را هم در اختیار معلم‌ها می‌گذارد؛ از ساخت آزمون و تصحیح خودکار تا تحلیل دقیق پیشرفت کلاس.
              </p>
            </div>

            <div dir="ltr" className="mt-8 grid grid-cols-4 gap-2">
              {TEACHER_FEATURES.map((feature, index) => (
                <FeatureIconButton
                  key={feature.title}
                  feature={feature}
                  active={index === activeIndex}
                  onActivate={() => setActiveIndex(index)}
                  compact
                />
              ))}
            </div>

            <div className="relative mt-8 aspect-[406/226] w-full">
              <div className="absolute -inset-1 rounded-[24px] bg-black/25 blur-md" />
              <div className="absolute inset-x-0 top-2 bottom-5 overflow-hidden rounded-t-[20px] border-[9px] border-[#07101c] bg-[#030711] shadow-[0_24px_45px_rgba(3,7,17,.42)]">
                <div className="relative h-full w-full overflow-hidden rounded-[10px] bg-[#030711]">
                  <TeacherScreen feature={activeFeature} mobile contain />
                </div>
              </div>
              <div className="absolute inset-x-0 bottom-0 h-6 rounded-b-[20px] bg-gradient-to-b from-[#111827] to-[#050a12]" />
              <div className="absolute bottom-[2px] left-1/2 h-2 w-24 -translate-x-1/2 rounded-b-xl bg-white/10" />
              <div className="absolute left-1/2 top-[-7px] z-20 flex -translate-x-1/2 items-center gap-1 rounded-t-md bg-[#030711] px-3 py-1.5 text-[9px] shadow-lg">
                مخصوص دبیران <Sparkles className="h-3 w-3" />
              </div>
            </div>

            <div dir="rtl" className="mt-6 min-h-[118px] rounded-2xl border border-white/15 bg-white/10 px-5 py-5 text-center backdrop-blur-md">
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeFeature.title}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.22 }}
                >
                  <h3 className="text-[23px] font-black leading-8">{activeFeature.title}</h3>
                  <p className="mt-3 text-[14px] leading-6 text-white/90 sm:text-[15px]">{activeFeature.description}</p>
                </motion.div>
              </AnimatePresence>
            </div>
          </div>

          <div className="relative hidden h-full md:block min-[1820px]:hidden">
            <div className="absolute inset-x-8 top-12 text-center">
              <h2 className="landing-display text-[40px] font-black leading-[1.3]">تدریست رو با هوش مصنوعی متحول کن</h2>
              <p className="mx-auto mt-5 max-w-[880px] text-[18px] font-medium leading-8 text-white/85">
                همان موتور هوشمندی که کنار دانش‌آموزهاست، حالا ابزارهای حرفه‌ای را هم در اختیار معلم‌ها می‌گذارد؛ از ساخت آزمون و تصحیح خودکار تا تحلیل دقیق پیشرفت کلاس.
              </p>
            </div>
            <div className="absolute left-1/2 top-[230px] h-[88px] w-[440px] -translate-x-1/2">
              <div dir="ltr" className="grid h-full grid-cols-4 gap-3">
                {TEACHER_FEATURES.map((feature, index) => (
                  <FeatureIconButton
                    key={feature.title}
                    feature={feature}
                    active={index === activeIndex}
                    onActivate={() => setActiveIndex(index)}
                  />
                ))}
              </div>
            </div>
            <div className="absolute left-1/2 top-[350px] h-[470px] w-[calc(100%_-_64px)] max-w-[880px] -translate-x-1/2">
              <div className="absolute -inset-1 rounded-[28px] bg-black/25 blur-md" />
              <div className="absolute inset-x-0 top-0 h-[430px] overflow-hidden rounded-t-[28px] border-[16px] border-[#07101c] bg-[#030711] shadow-[0_30px_70px_rgba(3,7,17,.45)]">
                <div className="relative h-full w-full overflow-hidden rounded-[10px]">
                  <TeacherScreen feature={activeFeature} />
                </div>
              </div>
              <div className="absolute inset-x-0 bottom-0 h-[44px] rounded-b-[28px] bg-gradient-to-b from-[#111827] to-[#050a12]" />
              <div className="absolute bottom-[2px] left-1/2 h-3 w-44 -translate-x-1/2 rounded-b-xl bg-white/10" />
              <div className="absolute left-1/2 top-[-22px] z-20 flex -translate-x-1/2 items-center gap-2 rounded-t-[10px] bg-black px-4 py-2 text-xs">
                مخصوص دبیران <Sparkles className="h-5 w-5" />
              </div>
            </div>
            <div dir="rtl" className="absolute inset-x-10 top-[850px] text-center">
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeFeature.title}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.22 }}
                >
                  <h3 className="text-[28px] font-black leading-9">{activeFeature.title}</h3>
                  <p className="mx-auto mt-3 max-w-[820px] text-base leading-7 text-white/85">{activeFeature.description}</p>
                </motion.div>
              </AnimatePresence>
            </div>
          </div>

          <div className="relative hidden h-full min-[1820px]:block">
            <div className="absolute left-[-192px] top-[84px] h-[600px] w-[1067px]">
              <div className="absolute -inset-1 rounded-[28px] bg-black/25 blur-md" />
              <div className="absolute inset-x-0 top-0 h-[560px] rounded-t-[28px] border-[18px] border-[#07101c] bg-[#030711] shadow-[0_30px_70px_rgba(3,7,17,.45)]">
                <div className="relative h-full w-full overflow-hidden rounded-[10px]">
                  <TeacherScreen feature={activeFeature} />
                </div>
              </div>
              <div className="absolute inset-x-0 bottom-0 h-[52px] rounded-b-[28px] bg-gradient-to-b from-[#111827] to-[#050a12]" />
              <div className="absolute bottom-[2px] left-1/2 h-3 w-44 -translate-x-1/2 rounded-b-xl bg-white/10" />
              <div className="absolute left-1/2 top-[-30px] z-20 flex -translate-x-1/2 items-center gap-2 rounded-t-[10px] bg-black px-4 py-2 text-sm">
                مخصوص دبیران <Sparkles className="h-6 w-6" />
              </div>
            </div>
            <div dir="rtl" className="absolute right-24 top-[103px] h-[153px] w-[777px] text-right">
              <h2 className="landing-display text-[48px] font-black leading-[67px]">تدریست رو با هوش مصنوعی متحول کن</h2>
              <p className="mt-6 text-[20px] font-medium leading-[31px] text-white/90">
                همان موتور هوشمندی که کنار دانش‌آموزهاست، حالا ابزارهای حرفه‌ای را هم در اختیار معلم‌ها می‌گذارد؛ از ساخت آزمون و تصحیح خودکار تا تحلیل دقیق پیشرفت کلاس.
              </p>
            </div>
            <div dir="rtl" className="absolute right-24 top-[288px] h-[376px] w-[777px]">
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
                    className={`block w-full overflow-hidden rounded-2xl text-right transition-all duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 ${
                      active
                        ? 'h-[136px] border-2 border-white/20 bg-white/15 p-6 shadow-[0_5px_14px_rgba(0,0,0,.10)] backdrop-blur-xl'
                        : 'h-20 border-2 border-transparent p-4 hover:bg-[#030711]/10'
                    }`}
                  >
                    <span className="flex items-center gap-6">
                      <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[#030711]/15">
                        <Icon className="h-6 w-6" />
                      </span>
                      <span className="text-[24px] font-bold leading-7">{feature.title}</span>
                    </span>
                    {active && <span className="mt-4 block pe-[72px] text-base leading-6 text-white/90">{feature.description}</span>}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
