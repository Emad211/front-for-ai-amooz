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

/** Figma nodes 277:390 / 336:3232 and mobile 244:1960 / 336:2892. */
export const HeroSection = ({ heroImage }: HeroSectionProps) => {
  return (
    <section className="landing-section-shell h-[964px] p-2 lg:h-dvh lg:min-h-[720px] lg:p-0">
      <div className="relative h-[956px] w-full overflow-hidden lg:h-full">
        <div className="absolute inset-x-0 bottom-0 top-[80px] overflow-hidden rounded-[20px] border border-[hsl(var(--landing-border)/.55)] bg-[hsl(var(--landing-hero))] shadow-[0_0_4px_hsl(var(--foreground)/.24)] lg:inset-x-8 lg:bottom-4 lg:top-24">
          <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="landing-dot-pattern absolute inset-0 opacity-80 [mask-image:radial-gradient(ellipse_at_center,black_16%,transparent_82%)]" />
            <div className="absolute -left-[19.8rem] -top-[19.8rem] h-[59.35rem] w-[59.35rem] rounded-full bg-primary/20 opacity-40 blur-[150px]" />
            <div className="absolute -bottom-16 -right-12 h-[27.6rem] w-[27.6rem] rounded-full bg-purple-500/10 opacity-40 blur-[60px]" />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_35%,hsl(var(--landing-hero))_92%)]" />
          </div>

          <div dir="ltr" className="relative flex h-full flex-col items-center justify-center gap-7 px-5 pb-7 pt-8 lg:-translate-y-3 lg:flex-row lg:gap-16 lg:px-24 lg:py-0">
            <motion.div
              initial={{ opacity: 0, scale: 0.97, x: -20 }}
              animate={{ opacity: 1, scale: 1, x: 0 }}
              transition={{ duration: 0.72, delay: 0.12 }}
              className="order-2 flex min-h-0 w-full flex-1 items-end justify-center lg:order-1 lg:h-[610px] lg:max-w-[792px]"
            >
              <div className="relative hidden h-[610px] w-full max-w-[792px] lg:block">
                <div className="absolute bottom-0 left-1/2 h-16 w-[76%] -translate-x-1/2 rounded-full bg-black/45 blur-2xl" />
                <Image
                  src={heroImage.imageUrl}
                  alt={heroImage.description}
                  width={792}
                  height={609}
                  priority
                  quality={95}
                  sizes="792px"
                  className="absolute bottom-px left-1/2 h-[609px] w-[792px] -translate-x-1/2 object-contain drop-shadow-[0_30px_48px_rgba(0,0,0,.48)]"
                />
                <Image
                  src="/landing/phone-toc-dark.png"
                  alt="نمای موبایل AI-Amooz"
                  width={129}
                  height={277}
                  priority
                  quality={95}
                  sizes="129px"
                  className="absolute bottom-0 right-0 h-[277px] w-[129px] object-contain drop-shadow-2xl"
                />
              </div>

              <div className="relative flex h-[305px] w-full max-w-[340px] items-end justify-center lg:hidden">
                <div className="absolute inset-x-8 bottom-4 h-16 rounded-full bg-primary/25 blur-3xl" />
                <Image
                  src="/landing/iphone-chat-dark.png"
                  alt="دستیار هوشمند AI-Amooz در موبایل"
                  width={243}
                  height={578}
                  priority
                  quality={95}
                  sizes="210px"
                  className="relative h-[305px] w-auto object-contain drop-shadow-[0_26px_42px_rgba(0,0,0,.5)]"
                />
              </div>
            </motion.div>

            <motion.div
              dir="rtl"
              initial={{ opacity: 0, y: 26 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.62 }}
              className="order-1 w-full text-center lg:order-2 lg:flex-1 lg:text-right"
            >
              <h1 className="landing-display mx-auto max-w-[760px] text-[40px] font-black leading-[1.28] text-foreground sm:text-5xl lg:mx-0 lg:text-[64px] lg:leading-[1.25]">
                آینده‌ی یادگیری را با هوش مصنوعی ما کامل کنید!
              </h1>
              <p className="mx-auto mt-6 max-w-[777px] text-[15px] font-medium leading-7 text-muted-foreground sm:text-lg lg:mx-0 lg:mt-8 lg:text-xl lg:leading-8">
                یادگیری یک سفر است و ما همسفر توایم؛ پا‌به‌پای تو محتوا را شخصی‌سازی می‌کنیم، نقاط ضعفت را پوشش می‌دهیم و مسئله حل می‌کنیم تا هرگز به بن‌بست نرسی.
              </p>

              <div className="mt-7 flex items-center justify-center gap-3 lg:mt-8 lg:justify-start lg:gap-4">
                <Button
                  asChild
                  variant="outline"
                  className="h-14 rounded-[10px] border-2 border-border/60 bg-transparent px-5 text-base backdrop-blur-sm hover:bg-card/60 sm:px-8 lg:h-16 lg:px-[42px] lg:text-xl"
                >
                  <Link href="#features">
                    <Play className="h-4 w-4 fill-current" />
                    بیشتر بدانید
                  </Link>
                </Button>
                <Button
                  asChild
                  className="group h-14 rounded-[10px] bg-gradient-to-l from-primary to-primary/90 px-5 text-base text-white shadow-[0_25px_50px_-12px_hsl(var(--primary)/.3)] sm:px-8 lg:h-16 lg:px-10 lg:text-xl"
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
      </div>
    </section>
  );
};
