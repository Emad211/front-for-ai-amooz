'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowLeft, Rocket } from 'lucide-react';
import { Button } from '@/components/ui/button';

export const FinalCTASection = () => {
  return (
    <section className="landing-section-shell h-[552px] pt-10 lg:h-[768px] lg:p-0">
      <div className="relative mx-auto flex h-[512px] w-full max-w-[440px] items-center justify-center overflow-hidden lg:h-[768px] lg:max-w-[1920px]">
        <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="landing-dot-pattern absolute inset-0 opacity-55 [mask-image:radial-gradient(ellipse_at_center,black_12%,transparent_76%)]" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,hsl(var(--primary)/.08),transparent_62%)]" />
          <div className="absolute -left-44 top-1/2 h-[302px] w-[347px] -translate-y-1/2 rounded-full bg-primary/25 blur-[81px]" />
          <div className="absolute -right-44 top-1/2 h-[302px] w-[347px] -translate-y-1/2 rounded-full bg-primary/25 blur-[81px]" />
          <div className="absolute bottom-[-16rem] left-1/2 h-[34rem] w-[34rem] -translate-x-1/2 rotate-45 rounded-[5rem] bg-primary/10 blur-[115px]" />
        </div>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.62 }}
          className="relative flex flex-col items-center px-4 text-center"
        >
          <div className="flex h-[38px] items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-[17px] text-sm font-medium text-primary backdrop-blur-xl">
            همین حالا شروع کن
            <Rocket className="h-4 w-4" />
          </div>
          <h2 className="landing-display mt-8 max-w-[558px] text-[40px] font-black leading-[1.2] text-foreground lg:text-[64px]">
            مسیر یادگیری‌ات رو شروع کن
          </h2>
          <Button
            asChild
            className="group mt-10 h-16 rounded-[10px] bg-gradient-to-l from-primary to-primary/90 px-10 text-xl text-white shadow-[0_25px_50px_-12px_hsl(var(--primary)/.3)]"
          >
            <Link href="/start">
              شروع سفر
              <ArrowLeft className="h-5 w-5 transition-transform group-hover:-translate-x-1" />
            </Link>
          </Button>
        </motion.div>
      </div>
    </section>
  );
};
