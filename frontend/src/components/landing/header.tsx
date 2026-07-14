'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Logo } from '@/components/ui/logo';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { LANDING_NAV_LINKS } from '@/constants/navigation';

export const LandingHeader = () => {
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setIsScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header className="fixed inset-x-0 top-0 z-50 px-2 pt-6 sm:px-4 lg:px-8 lg:pt-10">
      <div
        className={`mx-auto flex h-10 w-full max-w-[1792px] items-center justify-between rounded-2xl px-6 transition-all duration-300 lg:px-0 ${
          isScrolled
            ? 'border border-border/60 bg-background/[.88] shadow-lg backdrop-blur-xl lg:px-5'
            : 'border border-transparent bg-transparent'
        }`}
      >
        <Link href="/" aria-label="AI-Amooz" className="order-1 shrink-0">
          <Logo imageSize="md" />
        </Link>

        <nav className="order-2 hidden items-center gap-8 lg:flex">
          {LANDING_NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="order-3 flex items-center gap-2">
          <div className="hidden lg:block">
            <ThemeToggle />
          </div>
          <div className="hidden items-center gap-2 sm:flex">
            <Button asChild variant="ghost" size="sm" className="h-9 rounded-[10px] text-muted-foreground">
              <Link href="/login">ورود</Link>
            </Button>
            <Button asChild size="sm" className="h-9 rounded-[10px] shadow-sm">
              <Link href="/start">شروع رایگان</Link>
            </Button>
          </div>

          <Sheet>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="h-10 w-10 rounded-xl lg:hidden" aria-label="بازکردن منو">
                <Menu className="h-6 w-6" />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[min(22rem,90vw)] border-border/60 bg-background/95 backdrop-blur-2xl">
              <SheetHeader className="mb-10 text-right">
                <SheetTitle><Logo /></SheetTitle>
              </SheetHeader>
              <nav className="flex flex-col gap-2">
                {LANDING_NAV_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className="rounded-xl px-4 py-3 text-lg font-semibold transition-colors hover:bg-muted hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  >
                    {link.label}
                  </Link>
                ))}
                <div className="my-3 h-px bg-border/60" />
                <div className="flex items-center justify-between rounded-xl px-4 py-3">
                  <span className="font-semibold">تغییر تم</span>
                  <ThemeToggle />
                </div>
                <Button asChild variant="outline" className="mt-4 h-12 rounded-xl">
                  <Link href="/login">ورود به حساب</Link>
                </Button>
                <Button asChild className="h-12 rounded-xl">
                  <Link href="/start">شروع رایگان</Link>
                </Button>
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
};
