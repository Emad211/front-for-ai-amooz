'use client';

import { motion } from 'framer-motion';
import {
  BarChart3,
  Bot,
  ClipboardCheck,
  LayoutGrid,
  MessageSquareText,
  Route,
  Sparkles,
  type LucideIcon,
} from 'lucide-react';

type Reason = {
  icon: LucideIcon;
  title: string;
  description: string;
  mobileHeight: string;
};

const REASONS: Reason[] = [
  {
    icon: Route,
    title: 'مسیر یادگیری شخصی',
    description:
      'هوش مصنوعی سطح دانش شما را می‌سنجد و بهترین مسیر آموزشی را برای رسیدن به اهداف‌تان طراحی می‌کند.',
    mobileHeight: 'h-52',
  },
  {
    icon: ClipboardCheck,
    title: 'آزمون‌های تطبیقی',
    description: 'آزمون‌هایی که بر اساس نقاط ضعف و قوت شما طراحی می‌شوند.',
    mobileHeight: 'h-[11.5rem]',
  },
  {
    icon: Bot,
    title: 'دستیار هوشمند',
    description:
      'در هر لحظه سوالات درسی بپرسید، راه‌حل‌های مختلف را بررسی کنید و اشکالات خود را رفع کنید.',
    mobileHeight: 'h-52',
  },
  {
    icon: LayoutGrid,
    title: 'مدیریت کلاس‌های مختلف',
    description:
      'تمام دوره‌ها، دانش‌آموزان و برنامه‌های آموزشی خود را بدون سردرگمی، در یک پنل مدیریت متمرکز و منظم دسته‌بندی کنید.',
    mobileHeight: 'h-52',
  },
  {
    icon: MessageSquareText,
    title: 'پیام به دانش‌آموز',
    description:
      'در لحظه با دانش‌آموزان خود در ارتباط باشید؛ بازخورد بدهید، به سوالات پاسخ دهید و انگیزه‌ی یادگیری را زنده نگه دارید.',
    mobileHeight: 'h-52',
  },
  {
    icon: BarChart3,
    title: 'آمار و تحلیل کلاس‌ها',
    description:
      'روند یادگیری را با نمودارهای دقیق زیر ذره‌بین بگیرید. نقاط قوت و ضعف هر کلاس را در یک نگاه تحلیل کنید.',
    mobileHeight: 'h-36',
  },
];

export const WhyUsSection = () => {
  return (
    <section
      id="why-us"
      className="landing-section-shell min-h-[1411px] px-2 py-10 sm:px-4 lg:h-[633px] lg:min-h-0 lg:px-8"
    >
      <div className="mx-auto flex w-full max-w-[1664px] flex-col items-center">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-[17px] py-[9px] text-sm font-medium text-primary"
        >
          چرا ما
          <Sparkles className="h-4 w-4" />
        </motion.div>

        <motion.h2
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.08 }}
          className="landing-display mt-11 text-center text-3xl font-black text-foreground sm:text-4xl lg:mt-8 lg:text-5xl"
        >
          چرا باید همسفر ما بشید؟
        </motion.h2>

        <div dir="ltr" className="mt-11 grid w-full grid-cols-1 lg:mt-8 lg:grid-cols-3 lg:grid-rows-[176px_176px] lg:gap-y-8">
          {REASONS.map((reason, index) => {
            const isDesktopDivider = index % 3 !== 2;
            const hasMobileDivider = index !== REASONS.length - 1;
            return (
              <motion.article
                dir="rtl"
                key={reason.title}
                initial={{ opacity: 0, y: 22 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-50px' }}
                transition={{ duration: 0.45, delay: (index % 3) * 0.07 }}
                className={`relative flex flex-col items-center justify-center px-4 text-center sm:px-8 lg:h-44 lg:px-8 ${reason.mobileHeight} ${
                  isDesktopDivider ? 'lg:border-r lg:border-border/50' : ''
                } ${hasMobileDivider ? 'border-b border-border/50 lg:border-b-0' : ''}`}
              >
                <div className="mb-3 flex h-9 w-9 items-center justify-center text-primary">
                  <reason.icon className="h-7 w-7" strokeWidth={1.65} />
                </div>
                <h3 className="text-2xl font-bold leading-10 text-foreground">{reason.title}</h3>
                <p className="mt-2 max-w-[29rem] text-base leading-6 text-muted-foreground">
                  {reason.description}
                </p>
              </motion.article>
            );
          })}
        </div>
      </div>
    </section>
  );
};
