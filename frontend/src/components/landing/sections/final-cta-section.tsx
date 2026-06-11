'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowLeft, Rocket } from 'lucide-react';
import { Button } from '@/components/ui/button';

/** Figma "contact us" / final CTA (node 277:612). */
export const FinalCTASection = () => {
  return (
    <section className="relative overflow-hidden py-20 md:py-32">
      {/* Emerald glow + the Figma diamond light-beam behind the headline */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute bottom-0 left-1/2 h-[28rem] w-[44rem] -translate-x-1/2 rounded-full bg-primary/15 blur-[130px]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom,hsl(var(--primary)/0.12),transparent_60%)]" />
        <div className="absolute left-1/2 top-1/2 hidden h-72 w-72 -translate-x-1/2 -translate-y-1/2 rotate-45 rounded-3xl bg-foreground/10 blur-[80px] dark:block md:h-96 md:w-96" />
        <div className="absolute left-1/2 top-1/2 hidden h-[34rem] w-[34rem] -translate-x-1/2 -translate-y-1/2 rotate-45 rounded-[4rem] bg-primary/10 blur-[110px] dark:block" />
      </div>

      <div className="container mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7 }}
          className="mx-auto max-w-2xl text-center"
        >
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary dark:border-white/10 dark:bg-[#070B15] dark:text-foreground">
            <Rocket className="h-4 w-4" />
            همین حالا شروع کن
          </div>

          <h2 className="text-4xl font-black leading-tight text-foreground md:text-5xl lg:text-6xl">
            مسیر یادگیری‌ات رو شروع کن
          </h2>

          <p className="mx-auto mt-5 max-w-xl text-base leading-8 text-muted-foreground md:text-lg">
            همین امروز همسفر ما شو؛ رایگان ثبت‌نام کن و اولین گام مسیر یادگیری هوشمندت را بردار.
          </p>

          <div className="mt-9 flex justify-center">
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
          </div>
        </motion.div>
      </div>
    </section>
  );
};
