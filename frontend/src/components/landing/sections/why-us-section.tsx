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

type Reason = (typeof REASONS)[number];

function ArtboardReasonCard({ reason, delay = 0 }: { reason: Reason; delay?: number }) {
  const Icon = reason.icon;

  return (
    <motion.article
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.42, delay }}
      className="relative h-full text-center"
    >
      <div className="absolute left-1/2 top-0 flex h-8 w-8 -translate-x-1/2 items-center justify-center text-primary">
        <Icon className="h-7 w-7" strokeWidth={1.65} />
      </div>
      <h3 className="absolute inset-x-0 top-11 h-10 text-2xl font-bold leading-10 text-foreground">{reason.title}</h3>
      <p className="absolute inset-x-0 top-24 mx-auto max-w-[29.35rem] text-base leading-6 text-muted-foreground">
        {reason.description}
      </p>
    </motion.article>
  );
}

function TabletReasonCard({ reason, delay = 0 }: { reason: Reason; delay?: number }) {
  const Icon = reason.icon;

  return (
    <motion.article
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.42, delay }}
      className="flex min-h-[220px] flex-col items-center justify-center rounded-[20px] border border-[hsl(var(--landing-border)/.55)] bg-[hsl(var(--landing-panel))] px-8 py-8 text-center shadow-[0_0_4px_hsl(var(--foreground)/.12)]"
    >
      <div className="flex h-10 w-10 items-center justify-center text-primary">
        <Icon className="h-8 w-8" strokeWidth={1.65} />
      </div>
      <h3 className="mt-4 text-2xl font-bold leading-10 text-foreground">{reason.title}</h3>
      <p className="mt-2 max-w-[30rem] text-base leading-7 text-muted-foreground">{reason.description}</p>
    </motion.article>
  );
}

export const WhyUsSection = () => {
  const mobileRows = [144, 120, 144, 144, 144, 144];
  const mobileOrder = [0, 1, 2, 3, 4, 5];
  const desktopOrder = [0, 1, 2, 4, 3, 5];

  return (
    <section id="why-us" className="landing-section-shell h-[1451px] px-2 pt-10 md:h-auto md:px-8 md:py-20 min-[1820px]:h-[633px] min-[1820px]:p-0">
      <div className="mx-auto h-[1411px] w-full max-w-[1920px] px-2 pt-10 md:h-auto md:max-w-[1200px] md:px-0 md:pt-0 min-[1820px]:h-[633px] min-[1820px]:max-w-[1920px] min-[1820px]:px-32 min-[1820px]:pt-10">
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
          className="landing-display mt-11 h-[45px] text-center text-[32px] font-black leading-[45px] text-foreground min-[1820px]:mt-8 min-[1820px]:h-[67px] min-[1820px]:text-[48px] min-[1820px]:leading-[67px]"
        >
          چرا باید همسفر ما بشید؟
        </motion.h2>

        {/* Exact 440px mobile artboard. */}
        <div className="mx-auto mt-11 h-[1160px] w-full max-w-[408px] md:hidden">
          {mobileOrder.map((reasonIndex, index) => (
            <div key={REASONS[reasonIndex]!.title}>
              <div style={{ height: mobileRows[index] }}>
                <ArtboardReasonCard reason={REASONS[reasonIndex]!} delay={(index % 3) * 0.05} />
              </div>
              {index < mobileOrder.length - 1 && (
                <div className="flex h-16 items-center">
                  <div className="h-px w-full bg-border/55" />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Intermediate widths are intentionally independent from both Figma artboards. */}
        <div className="mx-auto mt-12 hidden grid-cols-2 gap-6 md:grid min-[1820px]:hidden">
          {mobileOrder.map((reasonIndex, index) => (
            <TabletReasonCard
              key={REASONS[reasonIndex]!.title}
              reason={REASONS[reasonIndex]!}
              delay={(index % 2) * 0.06}
            />
          ))}
        </div>

        {/* Exact 1920px artboard; the 128px separator tracks place the rules at Figma x=533.333/1130.667. */}
        <div
          dir="ltr"
          className="mx-auto mt-8 hidden h-[384px] w-full max-w-[1664px] grid-rows-[176px_32px_176px] min-[1820px]:grid"
          style={{
            gridTemplateColumns:
              'minmax(0, 1fr) clamp(80px, 6.6667vw, 128px) minmax(0, 1fr) clamp(80px, 6.6667vw, 128px) minmax(0, 1fr)',
          }}
        >
          {desktopOrder.slice(0, 3).map((reasonIndex, index) => (
            <div key={REASONS[reasonIndex]!.title} className="col-span-1 row-start-1 h-44" style={{ gridColumn: index * 2 + 1 }}>
              <ArtboardReasonCard reason={REASONS[reasonIndex]!} delay={index * 0.06} />
            </div>
          ))}
          <div className="col-start-2 row-start-1 flex items-center justify-center"><div className="h-16 w-px bg-border/55" /></div>
          <div className="col-start-4 row-start-1 flex items-center justify-center"><div className="h-16 w-px bg-border/55" /></div>
          {desktopOrder.slice(3).map((reasonIndex, index) => (
            <div key={REASONS[reasonIndex]!.title} className="col-span-1 row-start-3 h-44" style={{ gridColumn: index * 2 + 1 }}>
              <ArtboardReasonCard reason={REASONS[reasonIndex]!} delay={index * 0.06} />
            </div>
          ))}
          <div className="col-start-2 row-start-3 flex items-center justify-center"><div className="h-16 w-px bg-border/55" /></div>
          <div className="col-start-4 row-start-3 flex items-center justify-center"><div className="h-16 w-px bg-border/55" /></div>
        </div>
      </div>
    </section>
  );
};
