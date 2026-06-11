'use client';

import Image from 'next/image';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowLeft, Play } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface HeroSectionProps {
  heroImage: {
    imageUrl: string;
    description: string;
  };
}

/**
 * Hero — Figma "1920w dark redesign" hero.
 * RTL two-column: headline + dual CTA on the right, Mac Studio + phone mockups
 * on the left (desktop only). Mobile shows a glowing brand mark instead of the
 * devices. Theme-aware via semantic tokens; mint = `primary`.
 */
export const HeroSection = ({ heroImage }: HeroSectionProps) => {
  return (
    <section className="relative overflow-hidden pt-32 pb-20 md:pt-40 md:pb-28">
      {/* Ambient glows — mint top-left (devices side), purple bottom-right (per Figma) */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -left-80 -top-80 h-[60rem] w-[60rem] rounded-full bg-primary/20 opacity-40 blur-[150px] animate-pulse-glow" />
        <div className="absolute -bottom-12 -right-12 h-[28rem] w-[28rem] rounded-full bg-purple-500/10 opacity-40 blur-[60px]" />
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
            {/* Mobile brand mark (Figma mobile hero shows the glowing logo, no devices) */}
            <div className="mb-8 flex justify-center lg:hidden">
              <div className="relative">
                <div className="absolute inset-0 -z-10 rounded-3xl bg-primary/30 blur-2xl" />
                <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded-3xl border border-primary/20 bg-card/60 backdrop-blur">
                  <Image
                    src="/logo.png"
                    alt="AI-Amooz"
                    width={96}
                    height={96}
                    className="h-full w-full scale-[1.9] object-contain"
                  />
                </div>
              </div>
            </div>

            <h1 className="text-4xl font-black leading-[1.25] tracking-tight text-foreground sm:text-5xl lg:text-6xl">
              آینده‌ی یادگیری را با{' '}
              <span className="bg-gradient-to-l from-primary to-emerald-400 bg-clip-text text-transparent dark:from-foreground dark:to-foreground">
                هوش مصنوعی
              </span>{' '}
              ما کامل کنید!
            </h1>

            <p className="mx-auto mt-6 max-w-xl text-base font-medium leading-8 text-muted-foreground md:text-lg lg:mx-0">
              یادگیری یک سفر است و ما همسفر توایم؛ مسیرت را شخصی‌سازی می‌کنیم،
              نقاط ضعف را پوشش می‌دهیم و همیشه کنارت می‌مانیم تا هرگز به بن‌بست نرسی.
            </p>

            <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center lg:justify-start">
              <Button
                asChild
                size="lg"
                className="group h-14 w-full rounded-[10px] px-10 text-lg shadow-[0_25px_50px_-12px_hsl(var(--primary)/0.3)] dark:bg-gradient-to-l dark:from-primary dark:to-primary/90 dark:text-white sm:w-auto md:h-16"
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
                className="h-14 w-full rounded-[10px] border-2 border-border/60 px-10 text-lg backdrop-blur-sm hover:border-primary/50 hover:bg-card/60 dark:border-[#253141]/50 dark:bg-transparent sm:w-auto md:h-16"
              >
                <Link href="#features">
                  <Play className="h-4 w-4 fill-current" />
                  بیشتر بدانید
                </Link>
              </Button>
            </div>
          </motion.div>

          {/* Device mockups (left in RTL) — Figma assets, desktop only */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.7, delay: 0.15 }}
            className="relative mx-auto hidden w-full max-w-xl lg:mx-0 lg:block"
          >
            {/* Mac Studio display with the dark class UI */}
            <Image
              src="/landing/mac-studio-dark.png"
              alt={heroImage.description}
              width={792}
              height={609}
              priority
              className="h-auto w-full drop-shadow-2xl"
            />

            {/* Floating phone overlapping the monitor's right edge (per Figma) */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.4 }}
              className="absolute -right-2 bottom-0 w-24 sm:w-28"
            >
              <Image
                src="/landing/phone-toc-dark.png"
                alt="AI-Amooz mobile preview"
                width={129}
                height={277}
                className="h-auto w-full drop-shadow-2xl"
              />
            </motion.div>
          </motion.div>
        </div>
      </div>
    </section>
  );
};
