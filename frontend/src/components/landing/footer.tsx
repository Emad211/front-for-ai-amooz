'use client';

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Instagram, Send, Mail, Heart, ArrowUp } from 'lucide-react';
import { SITE_CONFIG } from '@/constants/site';
import { LANDING_NAV_LINKS } from '@/constants/navigation';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';

/**
 * Footer — Figma "1920w dark redesign" footer: an inset rounded panel
 * (#070B15 in dark) with a subtle dot pattern, everything centered — logo
 * tile, nav links (stacked on mobile), three social buttons — then a divider
 * and the legal row with a scroll-to-top button.
 */
export function LandingFooter() {
  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const socials = [
    { href: SITE_CONFIG.links.telegram, icon: Send, label: 'تلگرام' },
    { href: SITE_CONFIG.links.instagram, icon: Instagram, label: 'اینستاگرام' },
    { href: `mailto:${SITE_CONFIG.links.email}`, icon: Mail, label: 'ایمیل' },
  ];

  return (
    <footer className="px-4 pb-6 sm:px-6">
      <div className="container mx-auto p-0">
        <div className="relative overflow-hidden rounded-[2rem] border border-border/60 bg-card/40 px-6 py-12 dark:bg-[#070B15] md:px-10 md:py-14">
          {/* Subtle dot pattern */}
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(hsl(var(--foreground)/0.05)_1px,transparent_1px)] [background-size:22px_22px]" />

          <div className="relative">
            {/* Brand mark */}
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="flex justify-center"
            >
              <Link
                href="/"
                aria-label="AI-Amooz"
                className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-2xl border border-primary/20 bg-primary/10"
              >
                <Image
                  src="/logo.png"
                  alt="AI-Amooz logo"
                  width={64}
                  height={64}
                  className="h-full w-full scale-[1.9] object-contain"
                />
              </Link>
            </motion.div>

            {/* Nav links — horizontal on desktop, stacked on mobile (per Figma) */}
            <nav className="mt-10 flex flex-col items-center gap-7 md:flex-row md:justify-center md:gap-12">
              {LANDING_NAV_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="text-base font-semibold text-foreground/80 transition-colors hover:text-primary"
                >
                  {link.label}
                </Link>
              ))}
            </nav>

            {/* Socials */}
            <div className="mt-10 flex justify-center gap-4">
              {socials.map((social) => (
                <a
                  key={social.label}
                  href={social.href}
                  aria-label={social.label}
                  className="flex h-11 w-11 items-center justify-center rounded-xl border border-border/60 bg-foreground/5 text-muted-foreground transition-all duration-300 hover:border-primary/50 hover:text-primary"
                >
                  <social.icon className="h-5 w-5" />
                </a>
              ))}
            </div>
          </div>

          {/* Bottom bar */}
          <div className="relative mt-12 border-t border-border/40 pt-8">
            {/* Desktop */}
            <div className="hidden items-center justify-between md:flex">
              <div className="flex items-center gap-4">
                <p className="text-sm text-muted-foreground">
                  &copy; {new Date().getFullYear()} AI-Amooz. تمام حقوق محفوظ است.
                </p>
                <span className="text-muted-foreground/30">|</span>
                <p className="flex items-center gap-1 text-sm text-muted-foreground">
                  ساخته شده با <Heart className="h-3.5 w-3.5 fill-red-500 text-red-500" /> در ایران
                </p>
              </div>
              <div className="flex items-center gap-6">
                <div className="flex gap-6 text-sm">
                  <Link href="#" className="text-muted-foreground transition-colors hover:text-primary">
                    حریم خصوصی
                  </Link>
                  <Link href="#" className="text-muted-foreground transition-colors hover:text-primary">
                    قوانین استفاده
                  </Link>
                  <Link href="/admin-login" className="text-muted-foreground transition-colors hover:text-primary">
                    پنل مدیریت
                  </Link>
                </div>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={scrollToTop}
                  aria-label="بازگشت به بالا"
                  className="h-10 w-10 rounded-xl border-border/50 bg-transparent hover:border-primary/50 hover:bg-primary/5"
                >
                  <ArrowUp className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Mobile — stacked, centered (per Figma mobile footer) */}
            <div className="md:hidden">
              <div className="flex justify-center gap-8 text-sm">
                <Link href="#" className="text-muted-foreground transition-colors hover:text-primary">
                  حریم خصوصی
                </Link>
                <Link href="#" className="text-muted-foreground transition-colors hover:text-primary">
                  قوانین استفاده
                </Link>
                <Link href="/admin-login" className="text-muted-foreground transition-colors hover:text-primary">
                  پنل مدیریت
                </Link>
              </div>
              <p className="mt-10 flex items-center justify-center gap-1 text-sm text-muted-foreground">
                ساخته شده با <Heart className="h-3.5 w-3.5 fill-red-500 text-red-500" /> در ایران
              </p>
              <span className="mx-auto mt-4 block h-px w-6 bg-border" />
              <div className="mt-4 flex items-center justify-between">
                <Button
                  variant="outline"
                  size="icon"
                  onClick={scrollToTop}
                  aria-label="بازگشت به بالا"
                  className="h-10 w-10 rounded-xl border-border/50 bg-transparent hover:border-primary/50 hover:bg-primary/5"
                >
                  <ArrowUp className="h-4 w-4" />
                </Button>
                <p className="text-xs text-muted-foreground">
                  &copy; {new Date().getFullYear()} AI-Amooz. تمام حقوق محفوظ است.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
