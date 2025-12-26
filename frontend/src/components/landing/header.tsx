'use client';

import Image from 'next/image';
import Link from 'next/link';
import { Button } from '@/components/ui/button';

export const LandingHeader = () => (
  <header className="fixed top-0 left-0 right-0 z-50 transition-all duration-300">
    <div className="absolute inset-0 bg-background/80 backdrop-blur-md border-b border-border/50"></div>
    <div className="container mx-auto px-4 py-4 relative">
      <div className="flex justify-between items-center">
        <Link href="/" className="flex items-center gap-3 group">
          <span className="text-lg font-semibold text-foreground whitespace-nowrap">AI-Amooz</span>
          <div className="relative h-12 w-12 rounded-xl bg-card/80 border border-border/50 overflow-hidden">
            <Image
              src="/logo (2).png"
              alt="AI-Amooz logo"
              fill
              sizes="48px"
              className="object-contain p-2"
              priority
            />
          </div>
        </Link>
        
        <nav className="hidden md:flex items-center gap-8">
          <Link href="#features" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            ویژگی‌ها
          </Link>
          <Link href="#how-it-works" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            نحوه کار
          </Link>
          <Link href="#faq" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            سوالات متداول
          </Link>
        </nav>
        
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground">
            <Link href="/login">ورود</Link>
          </Button>
          <Button asChild size="sm" className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm">
            <Link href="/login">شروع رایگان</Link>
          </Button>
        </div>
      </div>
    </div>
  </header>
);
