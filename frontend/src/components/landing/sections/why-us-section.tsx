'use client';

import { motion } from 'framer-motion';
import {
  Route,
  ClipboardCheck,
  Bot,
  MessagesSquare,
  LayoutGrid,
  BarChart3,
  Sparkles,
  type LucideIcon,
} from 'lucide-react';

/** Figma "why us?" (node 303:206) — six value props in a 3×2 grid. */
const REASONS: { icon: LucideIcon; title: string; description: string }[] = [
  {
    icon: Route,
    title: 'مسیر یادگیری شخصی',
    description:
      'هوش مصنوعی سطح دانش شما را می‌سنجد و بهترین مسیر آموزشی را برای رسیدن به اهداف‌تان طراحی می‌کند.',
  },
  {
    icon: ClipboardCheck,
    title: 'آزمون‌های تطبیقی',
    description: 'آزمون‌هایی که بر اساس نقاط ضعف و قوت شما طراحی می‌شوند.',
  },
  {
    icon: Bot,
    title: 'دستیار هوشمند',
    description:
      'در هر لحظه سوالات درسی بپرسید، راه‌حل‌های مختلف را بررسی کنید و اشکالات خود را رفع کنید.',
  },
  {
    icon: MessagesSquare,
    title: 'پیام به دانش‌آموز',
    description:
      'در لحظه با دانش‌آموزان خود در ارتباط باشید؛ بازخورد بدهید، به سوالات پاسخ دهید و انگیزه‌ی یادگیری را زنده نگه دارید.',
  },
  {
    icon: LayoutGrid,
    title: 'مدیریت کلاس‌های مختلف',
    description:
      'تمام دوره‌ها، دانش‌آموزان و برنامه‌های آموزشی خود را بدون سردرگمی، در یک پنل مدیریت متمرکز و منظم دسته‌بندی کنید.',
  },
  {
    icon: BarChart3,
    title: 'آمار و تحلیل کلاس‌ها',
    description:
      'روند یادگیری را با نمودارهای دقیق زیر ذره‌بین بگیرید. نقاط قوت و ضعف هر کلاس را در یک نگاه تحلیل کنید.',
  },
];

export const WhyUsSection = () => {
  return (
    <section id="why-us" className="relative overflow-hidden py-20 md:py-28">
      <div className="container mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mx-auto mb-14 max-w-3xl text-center"
        >
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary">
            <Sparkles className="h-4 w-4" />
            چرا ما
          </div>
          <h2 className="text-3xl font-black text-foreground md:text-5xl">
            چرا باید همسفر ما بشید؟
          </h2>
        </motion.div>

        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
          {REASONS.map((reason, index) => (
            <motion.div
              key={reason.title}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-50px' }}
              transition={{ duration: 0.45, delay: (index % 3) * 0.1 }}
              className={`px-6 text-center lg:px-8 ${
                index % 3 !== 0 ? 'lg:border-r lg:border-border/40' : ''
              }`}
            >
              <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-primary">
                <reason.icon className="h-7 w-7" />
              </div>
              <h3 className="mb-2 text-xl font-bold text-foreground">{reason.title}</h3>
              <p className="text-sm leading-7 text-muted-foreground">{reason.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};
