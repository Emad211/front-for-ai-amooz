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

function TeacherScreen({ feature, mobile = false }: { feature: TeacherFeature; mobile?: boolean }) {
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
          sizes={mobile ? '300px' : '995px'}
          quality={95}
          className="object-cover object-top"
        />
      </motion.div>
    </AnimatePresence>
  );
}

export const TeacherCtaSection = () => {
  const [activeIndex, setActiveIndex] = useState(2);
  const activeFeature = TEACHER_FEATURES[activeIndex] ?? TEACHER_FEATURES[2]!;

  return (
    <section id="teacher-tools" className="landing-section-shell h-[827px] px-2 pt-10 lg:h-[848px] lg:px-8 lg:py-10">
      <div className="mx-auto h-[787px] w-full max-w-[424px] lg:h-[768px] lg:max-w-[1856px]">
        <div className="relative h-full overflow-hidden rounded-[20px] bg-gradient-to-br from-emerald-600 to-teal-700 text-white shadow-[0_0_4px_hsl(var(--foreground)/.25)]">
          <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="absolute -bottom-48 -left-48 h-[40rem] w-[40rem] rounded-full bg-white/35 blur-[130px]" />
            <div className="absolute -right-40 -top-40 h-[32rem] w-[32rem] rounded-full bg-emerald-200/10 blur-[110px]" />
            <div className="absolute -bottom-[45rem] -right-[25rem] select-none text-[92rem] font-black leading-none text-white/[0.045]">*</div>
          </div>

          {/* Mobile artboard, node 327:2322 */}
          <div className="relative h-full lg:hidden">
            <div className="absolute left-2 right-2 top-10 h-[189px] text-center">
              <h2 className="landing-display text-[36px] font-black leading-[1.25]">تدریست رو با هوش مصنوعی متحول کن</h2>
              <p className="mt-5 text-[15px] font-medium leading-[25px] text-white/85">
                همان موتور هوشمندی که کنار دانش‌آموزهاست، حالا ابزارهای حرفه‌ای را هم در اختیار معلم‌ها می‌گذارد؛ از ساخت آزمون و تصحیح خودکار تا تحلیل دقیق پیشرفت کلاس.
              </p>
            </div>

            <div className="absolute left-2 right-2 top-[285px] h-[96px]">
              <div dir="ltr" className="grid h-full grid-cols-4 gap-2">
                {TEACHER_FEATURES.map((feature, index) => {
                  const Icon = feature.icon;
                  const active = index === activeIndex;
                  return (
                    <button
                      key={feature.title}
                      type="button"
                      aria-label={feature.title}
                      aria-pressed={active}
                      onClick={() => setActiveIndex(index)}
                      className={`flex h-24 items-center justify-center rounded-2xl transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 ${
                        active ? 'bg-white/20 shadow-lg' : 'bg-[#030711]/15 text-white/75'
                      }`}
                    >
                      <Icon className="h-6 w-6" />
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="absolute left-[9px] right-[9px] top-[413px] h-[210px]">
              <div className="absolute inset-x-0 bottom-0 h-4 rounded-b-[18px] bg-[#07101c] shadow-[0_18px_30px_rgba(3,7,17,.45)]" />
              <div className="absolute inset-x-0 top-0 h-[198px] overflow-hidden rounded-t-[18px] border-[9px] border-[#07101c] bg-[#030711]">
                <TeacherScreen feature={activeFeature} mobile />
              </div>
              <div className="absolute left-1/2 top-[-15px] z-20 flex -translate-x-1/2 items-center gap-1 rounded-t-md bg-[#030711] px-2 py-1 text-[8px]">
                مخصوص دبیران <Sparkles className="h-2.5 w-2.5" />
              </div>
            </div>

            <div dir="rtl" className="absolute left-2 right-2 top-[655px] h-[92px] text-center">
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeFeature.title}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.22 }}
                >
                  <h3 className="text-[24px] font-black leading-7">{activeFeature.title}</h3>
                  <p className="mt-4 text-[15px] leading-6 text-white/85">{activeFeature.description}</p>
                </motion.div>
              </AnimatePresence>
            </div>
          </div>

          {/* Desktop artboard, node 277:553 */}
          <div className="relative hidden h-full lg:block">
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
