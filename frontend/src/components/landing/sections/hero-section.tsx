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

export const HeroSection = ({ heroImage }: HeroSectionProps) => {
  return (
    <section className="landing-section-shell px-2 pb-10 pt-2 sm:px-4 sm:pt-24 lg:px-8 lg:pt-28">
      <div className="relative mx-auto flex min-h-[956px] w-full max-w-[1856px] items-center overflow-hidden rounded-[1.25rem] border border-border/55 bg-[hsl(var(--landing-hero))] px-5 pb-8 pt-24 shadow-[0_0_4px_hsl(var(--foreground)/.24)] sm:min-h-[52rem] sm:px-9 sm:py-14 lg:min-h-[65.5rem] lg:px-24 lg:py-16">
        <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="landing-dot-pattern absolute inset-0 opacity-70 [mask-image:radial-gradient(ellipse_at_center,black_10%,transparent_78%)]" />
          <div className="absolute -left-[20rem] -top-[20rem] h-[60rem] w-[60rem] rounded-full bg-primary/20 opacity-40 blur-[150px]" />
          <div className="absolute -bottom-20 -right-16 h-[28rem] w-[28rem] rounded-full bg-purple-500/10 blur-[70px]" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_35%,hsl(var(--landing-hero))_90%)]" />
        </div>

        <div dir="ltr" className="relative grid w-full items-center gap-6 sm:gap-12 lg:grid-cols-[1.05fr_.95fr] lg:gap-16">
          <motion.div
            initial={{ opacity: 0, scale: 0.96, x: -20 }}
            animate={{ opacity: 1, scale: 1, x: 0 }}
            transition={{ duration: 0.75, delay: 0.12 }}
            className="order-2 mx-auto w-full max-w-[49.5rem] lg:order-1"
          >
            <div className="relative hidden min-h-[38rem] items-end justify-center lg:flex">
              <div className="absolute bottom-3 left-1/2 h-16 w-[78%] -translate-x-1/2 rounded-full bg-black/45 blur-2xl" />
              <Image
                src={heroImage.imageUrl}
                alt={heroImage.description}
                width={792}
                height={609}
                priority
                quality={90}
                sizes="(min-width: 1024px) 50vw, 0px"
                className="relative h-auto w-full object-contain drop-shadow-[0_30px_48px_rgba(0,0,0,.48)]"
              />
              <motion.div
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.45 }}
                className="absolute bottom-0 right-0 w-[8rem]"
              >
                <Image
                  src="/landing/phone-toc-dark.png"
                  alt="نمای موبایل AI-Amooz"
                  width={129}
                  height={277}
                  quality={90}
                  sizes="128px"
                  className="h-auto w-full drop-shadow-2xl"
                />
              </motion.div>
            </div>

            <div className="relative mx-auto flex h-[21rem] max-w-[22rem] items-end justify-center sm:h-[27rem] lg:hidden">
              <div className="absolute inset-x-2 bottom-6 h-20 rounded-full bg-primary/25 blur-3xl" />
              <Image
                src="/landing/iphone-chat-dark.png"
                alt="دستیار هوشمند AI-Amooz در موبایل"
                width={243}
                height={525}
                priority
                quality={90}
                sizes="(max-width: 639px) 220px, 243px"
                className="relative h-full w-auto object-contain drop-shadow-[0_28px_44px_rgba(0,0,0,.5)]"
              />
            </div>
          </motion.div>

          <motion.div
            dir="rtl"
            initial={{ opacity: 0, y: 28 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.65 }}
            className="order-1 text-center lg:order-2 lg:text-right"
          >
            <h1 className="landing-display text-[2.65rem] font-black leading-[1.25] text-foreground sm:text-6xl lg:text-[4rem]">
              آینده‌ی یادگیری را با هوش مصنوعی ما کامل کنید!
            </h1>
            <p className="mx-auto mt-7 max-w-[48rem] text-base font-medium leading-8 text-muted-foreground sm:text-lg lg:mx-0 lg:text-xl">
              یادگیری یک سفر است و ما همسفر توایم؛ پا‌به‌پای تو محتوا را شخصی‌سازی می‌کنیم، نقاط ضعفت را پوشش می‌دهیم و مسئله حل می‌کنیم تا هرگز به بن‌بست نرسی.
            </p>

            <div className="mt-9 flex flex-col-reverse items-stretch justify-center gap-4 sm:flex-row lg:justify-start">
              <Button
                asChild
                variant="outline"
                className="h-16 rounded-[10px] border-2 border-border/60 bg-transparent px-10 text-lg backdrop-blur-sm hover:bg-card/60"
              >
                <Link href="#features">
                  <Play className="h-4 w-4 fill-current" />
                  بیشتر بدانید
                </Link>
              </Button>
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
        </div>
      </div>
    </section>
  );
};
