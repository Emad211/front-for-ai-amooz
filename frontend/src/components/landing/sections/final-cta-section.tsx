'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowLeft, Rocket } from 'lucide-react';
import { Button } from '@/components/ui/button';

export const FinalCTASection = () => {
  return (
    <section className="landing-section-shell relative min-h-[32rem] overflow-hidden px-4 py-20 lg:min-h-[48rem] lg:px-8 lg:py-36">
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="landing-dot-pattern absolute inset-0 opacity-60 [mask-image:radial-gradient(ellipse_at_center,black_10%,transparent_72%)]" />
        <div className="absolute -bottom-24 left-1/2 h-[30rem] w-[48rem] -translate-x-1/2 rounded-full bg-primary/15 blur-[130px]" />
        <div className="absolute -left-36 top-1/2 h-72 w-72 -translate-y-1/2 rounded-full bg-primary/20 blur-[100px]" />
        <div className="absolute -right-36 top-1/2 h-72 w-72 -translate-y-1/2 rounded-full bg-primary/20 blur-[100px]" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 28 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-80px' }}
        transition={{ duration: 0.65 }}
        className="relative mx-auto flex max-w-3xl flex-col items-center text-center"
      >
        <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-[17px] py-[9px] text-sm font-medium text-primary">
          همین حالا شروع کن
          <Rocket className="h-4 w-4" />
        </div>
        <h2 className="landing-display mt-8 max-w-[36rem] text-4xl font-black leading-[1.2] text-foreground sm:text-5xl lg:text-6xl">
          مسیر یادگیری‌ات رو شروع کن
        </h2>
        <div className="mt-10">
          <Button
            asChild
            className="group h-16 rounded-[10px] bg-gradient-to-l from-primary to-primary/90 px-10 text-lg text-white shadow-[0_25px_50px_-12px_hsl(var(--primary)/.3)]"
          >
            <Link href="/start">
              شروع سفر
              <ArrowLeft className="h-5 w-5 transition-transform group-hover:-translate-x-1" />
            </Link>
          </Button>
        </div>
      </motion.div>
    </section>
  );
};
