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

const REASONS: Array<{
  icon: LucideIcon;
  title: string;
  description: string;
}> = [
  {
    icon: Route,
    title: 'مسیر یادگیری شخصی',
    description: 'هوش مصنوعی سطح دانش شما را می‌سنجد و بهترین مسیر آموزشی را برای رسیدن به اهداف‌تان طراحی می‌کند.',
  },
  {
    icon: ClipboardCheck,
    title: 'آزمون‌های تطبیقی',
    description: 'آزمون‌هایی که بر اساس نقاط ضعف و قوت شما طراحی می‌شوند.',
  },
  {
    icon: Bot,
    title: 'دستیار هوشمند',
    description: 'در هر لحظه سوالات درسی بپرسید، راه‌حل‌های مختلف را بررسی کنید و اشکالات خود را رفع کنید.',
  },
  {
    icon: LayoutGrid,
    title: 'مدیریت کلاس‌های مختلف',
    description: 'تمام دوره‌ها، دانش‌آموزان و برنامه‌های آموزشی خود را بدون سردرگمی، در یک پنل مدیریت متمرکز و منظم دسته‌بندی کنید.',
  },
  {
    icon: MessageSquareText,
    title: 'پیام به دانش‌آموز',
    description: 'در لحظه با دانش‌آموزان خود در ارتباط باشید؛ بازخورد بدهید، به سوالات پاسخ دهید و انگیزه‌ی یادگیری را زنده نگه دارید.',
  },
  {
    icon: BarChart3,
    title: 'آمار و تحلیل کلاس‌ها',
    description: 'روند یادگیری را با نمودارهای دقیق زیر ذره‌بین بگیرید. نقاط قوت و ضعف هر کلاس را در یک نگاه تحلیل کنید.',
  },
];

function ReasonCard({ reason, delay = 0 }: { reason: (typeof REASONS)[number]; delay?: number }) {
  const Icon = reason.icon;
  return (
    <motion.article
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.42, delay }}
      className="flex h-full flex-col items-center justify-center text-center"
    >
      <div className="flex h-8 w-8 items-center justify-center text-primary">
        <Icon className="h-7 w-7" strokeWidth={1.65} />
      </div>
      <h3 className="mt-3 text-2xl font-bold leading-10 text-foreground">{reason.title}</h3>
      <p className="mt-1 max-w-[29.35rem] text-base leading-6 text-muted-foreground">{reason.description}</p>
    </motion.article>
  );
}

export const WhyUsSection = () => {
  const mobileRows = [144, 120, 144, 144, 144, 144];
  const mobileOrder = [0, 1, 2, 3, 4, 5];
  const desktopOrder = [0, 1, 2, 4, 3, 5];

  return (
    <section id="why-us" className="landing-section-shell h-[1451px] px-2 pt-10 lg:h-[633px] lg:p-0">
      <div className="mx-auto h-[1411px] w-full max-w-[1920px] px-2 pt-10 lg:h-[633px] lg:px-32">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto flex h-[38px] w-fit items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-[17px] text-sm font-medium text-primary"
        >
          چرا ما
          <Sparkles className="h-4 w-4" />
        </motion.div>

        <motion.h2
          initial={{ opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.06 }}
          className="landing-display mt-11 h-[45px] text-center text-[32px] font-black leading-[45px] text-foreground lg:h-[67px] lg:text-[48px] lg:leading-[67px]"
        >
          چرا باید همسفر ما بشید؟
        </motion.h2>

        <div className="mx-auto mt-11 h-[1160px] w-full max-w-[408px] lg:hidden">
          {mobileOrder.map((reasonIndex, index) => (
            <div key={REASONS[reasonIndex]!.title}>
              <div style={{ height: mobileRows[index] }}>
                <ReasonCard reason={REASONS[reasonIndex]!} delay={(index % 3) * 0.05} />
              </div>
              {index < mobileOrder.length - 1 && (
                <div className="flex h-16 items-center">
                  <div className="h-px w-full bg-border/55" />
                </div>
              )}
            </div>
          ))}
        </div>

        <div dir="ltr" className="mx-auto mt-8 hidden h-[384px] w-full max-w-[1664px] grid-cols-[469.333px_64px_469.333px_64px_469.333px] grid-rows-[176px_32px_176px] lg:grid">
          {desktopOrder.slice(0, 3).map((reasonIndex, index) => (
            <div key={REASONS[reasonIndex]!.title} className="col-span-1 row-start-1 h-44" style={{ gridColumn: index * 2 + 1 }}>
              <ReasonCard reason={REASONS[reasonIndex]!} delay={index * 0.06} />
            </div>
          ))}
          <div className="col-start-2 row-start-1 flex items-center justify-center"><div className="h-16 w-px bg-border/55" /></div>
          <div className="col-start-4 row-start-1 flex items-center justify-center"><div className="h-16 w-px bg-border/55" /></div>

          {desktopOrder.slice(3).map((reasonIndex, index) => (
            <div key={REASONS[reasonIndex]!.title} className="col-span-1 row-start-3 h-44" style={{ gridColumn: index * 2 + 1 }}>
              <ReasonCard reason={REASONS[reasonIndex]!} delay={index * 0.06} />
            </div>
          ))}
          <div className="col-start-2 row-start-3 flex items-center justify-center"><div className="h-16 w-px bg-border/55" /></div>
          <div className="col-start-4 row-start-3 flex items-center justify-center"><div className="h-16 w-px bg-border/55" /></div>
        </div>
      </div>
    </section>
  );
};
