'use client';

import Image from 'next/image';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  GraduationCap,
  Users,
  Wand2,
  PenLine,
  LineChart,
  ArrowLeft,
  type LucideIcon,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

/** Figma "questions" / teacher section (node 277:553) — the mint teacher CTA. */
const ROWS: {
  icon: LucideIcon;
  title: string;
  description?: string;
  highlight?: boolean;
}[] = [
  { icon: Users, title: 'مدیریت کلاس و دانش‌آموزان' },
  { icon: Wand2, title: 'ساخت آزمون با هوش مصنوعی' },
  {
    icon: PenLine,
    title: 'تصحیح و نمره‌دهی خودکار',
    description: 'پاسخ‌ها را هوش مصنوعی تصحیح می‌کند و برای هر دانش‌آموز بازخورد می‌نویسد.',
    highlight: true,
  },
  { icon: LineChart, title: 'داشبورد تحلیل پیشرفت' },
];

export const TeacherCtaSection = () => {
  return (
    <section className="relative overflow-hidden py-20 md:py-28">
      <div className="container mx-auto px-4">
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-emerald-700 to-teal-900 p-6 shadow-2xl md:p-12">
          {/* Ambient glow */}
          <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-emerald-400/20 blur-[100px]" />
          <div className="pointer-events-none absolute -bottom-24 -left-20 h-72 w-72 rounded-full bg-teal-300/10 blur-[100px]" />

          <div className="relative grid items-center gap-10 lg:grid-cols-2">
            {/* Laptop mockup (left in RTL) */}
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.6 }}
              className="order-last lg:order-first"
            >
              <div className="mx-auto w-full max-w-lg">
                <div className="rounded-t-xl border-4 border-black/50 bg-black/50 p-1.5 shadow-2xl">
                  <div className="overflow-hidden rounded-md border border-white/10">
                    <Image
                      src="/landing.png"
                      alt="پنل دبیران AI-Amooz"
                      width={900}
                      height={560}
                      className="h-auto w-full object-cover"
                    />
                  </div>
                </div>
                <div className="mx-auto h-2 w-[108%] -translate-x-[3.7%] rounded-b-xl bg-black/60" />
              </div>
            </motion.div>

            {/* Text + checklist (right in RTL) */}
            <motion.div
              initial={{ opacity: 0, x: 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.6 }}
              className="text-white"
            >
              <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-1.5 text-sm font-medium text-emerald-50">
                <GraduationCap className="h-4 w-4" />
                مخصوص دبیران
              </div>

              <h2 className="text-3xl font-black leading-snug md:text-4xl">
                تدریست رو با هوش مصنوعی متحول کن
              </h2>
              <p className="mt-4 text-sm leading-7 text-white/80 md:text-base">
                همون موتور هوشمندی که کنار دانش‌آموزهاست، حالا ابزارهای حرفه‌ای رو هم در اختیار
                معلم‌ها می‌ذاره؛ از ساخت آزمون و تصحیح خودکار تا تحلیل دقیق پیشرفت کلاس.
              </p>

              <ul className="mt-8 space-y-3">
                {ROWS.map((row, index) => (
                  <motion.li
                    key={row.title}
                    initial={{ opacity: 0, y: 16 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.4, delay: index * 0.08 }}
                    className={`rounded-2xl border p-4 transition-colors ${
                      row.highlight
                        ? 'border-emerald-300/60 bg-white/10 shadow-lg shadow-emerald-900/30'
                        : 'border-white/10 bg-black/15 hover:bg-black/25'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-400/20 text-emerald-100">
                        <row.icon className="h-5 w-5" />
                      </span>
                      <span className="font-semibold">{row.title}</span>
                    </div>
                    {row.description && (
                      <p className="mt-2 pr-[3.25rem] text-sm leading-6 text-white/70">{row.description}</p>
                    )}
                  </motion.li>
                ))}
              </ul>

              <Button
                asChild
                size="lg"
                className="group mt-8 h-12 bg-white px-8 text-emerald-800 hover:bg-emerald-50"
              >
                <Link href="/start">
                  شروع تدریس با AI-Amooz
                  <ArrowLeft className="h-5 w-5 transition-transform group-hover:-translate-x-1" />
                </Link>
              </Button>
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
};
