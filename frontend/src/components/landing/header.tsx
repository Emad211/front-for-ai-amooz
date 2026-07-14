'use client';

import Link from 'next/link';
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

/**
 * Figma header: desktop 1792×40 at x=64/y=40; mobile 376×40 at x=24/y=24.
 * It intentionally lives inside the hero stage instead of floating over the page.
 */
export const LandingHeader = () => {
  return (
    <header className="absolute inset-x-0 top-0 z-50 px-6 pt-6 lg:px-16 lg:pt-10">
      <div dir="ltr" className="mx-auto flex h-10 w-full max-w-[1792px] items-center justify-between">
        <div className="hidden h-10 items-center gap-3 lg:flex">
          <div className="flex items-center gap-2">
            <Button asChild size="sm" className="h-9 rounded-[10px] px-3 text-sm shadow-sm">
              <Link href="/start">شروع رایگان</Link>
            </Button>
            <Button asChild variant="ghost" size="sm" className="h-9 rounded-[10px] px-3 text-sm text-muted-foreground">
              <Link href="/login">ورود</Link>
            </Button>
          </div>
          <ThemeToggle />
        </div>

        <nav dir="rtl" className="hidden items-center gap-8 lg:flex">
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

        <div className="flex w-full items-center justify-between lg:w-auto lg:justify-end">
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
              <nav dir="rtl" className="flex flex-col gap-2 text-right">
                {LANDING_NAV_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className="rounded-xl px-4 py-3 text-lg font-semibold transition-colors hover:bg-muted hover:text-primary"
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

          <Link href="/" aria-label="AI-Amooz" className="shrink-0">
            <Logo imageSize="md" />
          </Link>
        </div>
      </div>
    </header>
  );
};
