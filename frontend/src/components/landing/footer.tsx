'use client';

import Image from 'next/image';
import Link from 'next/link';
import { ArrowUp, Heart, Instagram, Mail, Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { LANDING_NAV_LINKS } from '@/constants/navigation';
import { SITE_CONFIG } from '@/constants/site';

export function LandingFooter() {
  const scrollToTop = () => window.scrollTo({ top: 0, behavior: 'smooth' });
  const socials = [
    { href: SITE_CONFIG.links.telegram, icon: Send, label: 'تلگرام' },
    { href: SITE_CONFIG.links.instagram, icon: Instagram, label: 'اینستاگرام' },
    { href: `mailto:${SITE_CONFIG.links.email}`, icon: Mail, label: 'ایمیل' },
  ];

  return (
    <footer className="landing-section-shell px-2 py-10 sm:px-4 lg:px-8">
      <div className="landing-panel landing-dot-pattern mx-auto w-full max-w-[1856px] overflow-hidden px-5 py-10 sm:px-10 lg:px-24">
        <div className="relative flex flex-col items-center">
          <Link
            href="/"
            aria-label="AI-Amooz"
            className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-xl border border-border/60 bg-background shadow-lg"
          >
            <Image src="/logo.png" alt="AI-Amooz" width={64} height={64} className="h-full w-full scale-[1.9] object-contain" />
          </Link>

          <nav className="mt-10 flex flex-col items-center gap-7 sm:flex-row sm:gap-12 lg:gap-16">
            {LANDING_NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-lg font-bold text-muted-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary lg:text-2xl"
              >
                {link.label}
              </Link>
            ))}
          </nav>

          <div className="mt-10 flex items-center gap-4 sm:gap-8">
            {socials.map((social) => {
              const isAvailable = Boolean(social.href && social.href !== '#');
              const Icon = social.icon;
              const className =
                'flex h-11 w-11 items-center justify-center rounded-xl border border-border/60 bg-card/60 text-muted-foreground transition-all';

              return isAvailable ? (
                <a
                  key={social.label}
                  href={social.href}
                  aria-label={social.label}
                  className={`${className} hover:border-primary/50 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary`}
                >
                  <Icon className="h-5 w-5" />
                </a>
              ) : (
                <span
                  key={social.label}
                  aria-label={`${social.label}؛ به‌زودی`}
                  aria-disabled="true"
                  title={`${social.label}؛ به‌زودی`}
                  className={`${className} cursor-not-allowed opacity-45`}
                >
                  <Icon className="h-5 w-5" />
                </span>
              );
            })}
          </div>
        </div>

        <div className="relative mt-12 border-t border-border/50 pt-8">
          <div className="hidden items-center justify-between md:flex">
            <div className="flex items-center gap-6">
              <Button
                variant="outline"
                size="icon"
                onClick={scrollToTop}
                aria-label="بازگشت به بالا"
                className="h-10 w-10 rounded-xl bg-background"
              >
                <ArrowUp className="h-4 w-4" />
              </Button>
              <span title="به‌زودی" className="cursor-default text-sm text-muted-foreground/70">قوانین استفاده</span>
              <span title="به‌زودی" className="cursor-default text-sm text-muted-foreground/70">حریم خصوصی</span>
            </div>

            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                ساخته شده با <Heart className="h-3.5 w-3.5 fill-red-500 text-red-500" /> در ایران
              </span>
              <span className="text-border">|</span>
              <span>© {new Date().getFullYear()} AI-Amooz. تمام حقوق محفوظ است.</span>
            </div>
          </div>

          <div className="flex flex-col items-center gap-7 text-center md:hidden">
            <div className="flex items-center justify-center gap-8 text-sm">
              <span title="به‌زودی" className="cursor-default text-muted-foreground/70">قوانین استفاده</span>
              <span title="به‌زودی" className="cursor-default text-muted-foreground/70">حریم خصوصی</span>
            </div>
            <span className="flex items-center gap-1 text-sm text-muted-foreground">
              ساخته شده با <Heart className="h-3.5 w-3.5 fill-red-500 text-red-500" /> در ایران
            </span>
            <div className="flex w-full items-center justify-between">
              <Button
                variant="outline"
                size="icon"
                onClick={scrollToTop}
                aria-label="بازگشت به بالا"
                className="h-10 w-10 rounded-xl bg-background"
              >
                <ArrowUp className="h-4 w-4" />
              </Button>
              <span className="text-xs text-muted-foreground">
                © {new Date().getFullYear()} AI-Amooz. تمام حقوق محفوظ است.
              </span>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
