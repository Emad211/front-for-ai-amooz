'use client';

import Image from 'next/image';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowLeft, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface HeroSectionProps {
  heroImage: {
    imageUrl: string;
    description: string;
  };
}

/**
 * Hero — Figma "hero" (node 277:390).
 * RTL two-column: headline + dual CTA on the right, device mockups on the left.
 * Theme-aware (dark/light) via semantic tokens; mint = `primary`.
 */
export const HeroSection = ({ heroImage }: HeroSectionProps) => {
  return (
    <section className="relative overflow-hidden pt-32 pb-20 md:pt-40 md:pb-28">
      {/* Ambient mint glows */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -top-40 right-0 h-[32rem] w-[32rem] rounded-full bg-primary/20 blur-[120px] animate-pulse-glow" />
        <div className="absolute bottom-0 left-0 h-[28rem] w-[28rem] rounded-full bg-primary/10 blur-[120px]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,transparent_45%,hsl(var(--background)))]" />
      </div>

      <div className="container mx-auto px-4">
        <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-8">
          {/* Text block (right in RTL) */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-center lg:text-right"
          >
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary">
              <Sparkles className="h-4 w-4" />
              پلتفرم آموزشی هوشمند
            </div>

            <h1 className="text-4xl font-black leading-[1.25] tracking-tight text-foreground sm:text-5xl lg:text-6xl">
              آینده‌ی یادگیری را با{' '}
              <span className="bg-gradient-to-l from-primary to-emerald-400 bg-clip-text text-transparent">
                هوش مصنوعی
              </span>{' '}
              ما کامل کنید!
            </h1>

            <p className="mx-auto mt-6 max-w-xl text-base leading-8 text-muted-foreground md:text-lg lg:mx-0">
              یادگیری یک سفر است و ما همسفر توایم؛ مسیرت را شخصی‌سازی می‌کنیم،
              نقاط ضعف را پوشش می‌دهیم و همیشه کنارت می‌مانیم تا هرگز به بن‌بست نرسی.
            </p>

            <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center lg:justify-start">
              <Button
                asChild
                size="lg"
                className="group h-14 w-full px-8 text-lg shadow-lg shadow-primary/25 sm:w-auto"
              >
                <Link href="/start">
                  شروع سفر
                  <ArrowLeft className="h-5 w-5 transition-transform group-hover:-translate-x-1" />
                </Link>
              </Button>
              <Button
                asChild
                variant="outline"
                size="lg"
                className="h-14 w-full border-border/60 px-8 text-lg backdrop-blur-sm hover:border-primary/50 hover:bg-card/60 sm:w-auto"
              >
                <Link href="#features">بیشتر بدانید</Link>
              </Button>
            </div>
          </motion.div>

          {/* Device mockups (left in RTL) */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.7, delay: 0.15 }}
            className="relative mx-auto w-full max-w-xl lg:mx-0"
          >
            {/* Monitor */}
            <div className="relative rounded-2xl border border-border/60 bg-card/70 p-2 shadow-2xl shadow-primary/10 backdrop-blur">
              <div className="flex items-center gap-1.5 px-3 py-2">
                <span className="h-2.5 w-2.5 rounded-full bg-destructive/70" />
                <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
                <span className="h-2.5 w-2.5 rounded-full bg-primary/70" />
              </div>
              <div className="overflow-hidden rounded-xl border border-border/40">
                <Image
                  src={heroImage.imageUrl}
                  alt={heroImage.description}
                  width={900}
                  height={600}
                  priority
                  className="h-auto w-full object-cover"
                />
              </div>
            </div>

            {/* Floating phone */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.4 }}
              className="absolute -bottom-8 -left-4 w-28 sm:w-36"
            >
              <div className="aspect-[9/19] overflow-hidden rounded-[1.75rem] border-4 border-card bg-card shadow-2xl shadow-black/40">
                <Image
                  src="/homee.png"
                  alt="AI-Amooz mobile preview"
                  width={200}
                  height={420}
                  className="h-full w-full object-cover"
                />
              </div>
            </motion.div>
          </motion.div>
        </div>
      </div>
    </section>
  );
};
