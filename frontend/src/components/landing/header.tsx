'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Menu, X, Sun, Moon } from 'lucide-react';
import { useTheme } from 'next-themes';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

const ThemeToggle = () => {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="w-9 h-9" />;

  return (
    <Button 
      variant="ghost" 
      size="icon" 
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      className="rounded-full w-9 h-9"
    >
      {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
    </Button>
  );
};

export const LandingHeader = () => {
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navLinks = [
    { href: "#features", label: "ویژگی‌ها" },
    { href: "#how-it-works", label: "نحوه کار" },
    { href: "#faq", label: "سوالات متداول" },
  ];

  return (
    <header className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${isScrolled ? 'py-2' : 'py-4'}`}>
      <div className={`absolute inset-0 transition-all duration-300 ${isScrolled ? 'bg-background/90 backdrop-blur-lg border-b border-border/50 shadow-sm' : 'bg-transparent'}`}></div>
      <div className="container mx-auto px-4 relative">
        <div className="flex justify-between items-center">
          {/* Logo Section */}
          <Link href="/" className="flex items-center gap-2 group relative">
            <div className="relative h-10 w-14 md:h-12 md:w-16">
              <Image
                src="/logo (2).png"
                alt="AI-Amooz logo"
                fill
                sizes="(max-width: 768px) 100px, 128px"
                className="object-contain transition-all duration-300 scale-[2] md:scale-[2.2] origin-center"
                priority
              />
            </div>
            <span className="text-xl md:text-2xl font-bold text-foreground whitespace-nowrap tracking-tighter ml-2">AI-Amooz</span>
          </Link>
          
          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-8">
            {navLinks.map((link) => (
              <Link 
                key={link.href}
                href={link.href} 
                className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors"
              >
                {link.label}
              </Link>
            ))}
          </nav>
          
          {/* Actions */}
          <div className="flex items-center gap-2 md:gap-3">
            <div className="hidden md:block">
              <ThemeToggle />
            </div>
            <div className="hidden sm:flex items-center gap-2">
              <Button asChild variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground">
                <Link href="/login">ورود</Link>
              </Button>
              <Button asChild size="sm" className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm">
                <Link href="/login">شروع رایگان</Link>
              </Button>
            </div>

            {/* Mobile Menu */}
            <div className="md:hidden">
              <Sheet>
                <SheetTrigger asChild>
                  <Button variant="ghost" size="icon" className="text-foreground">
                    <Menu className="h-6 w-6" />
                  </Button>
                </SheetTrigger>
                <SheetContent side="right" className="w-[300px] bg-background/95 backdrop-blur-xl border-l border-border/50">
                  <SheetHeader className="text-right mb-8">
                    <SheetTitle className="text-2xl font-bold tracking-tighter text-primary">AI-Amooz</SheetTitle>
                  </SheetHeader>
                  <nav className="flex flex-col gap-6 text-right">
                    {navLinks.map((link) => (
                      <Link 
                        key={link.href}
                        href={link.href} 
                        className="text-lg font-medium text-foreground hover:text-primary transition-colors"
                      >
                        {link.label}
                      </Link>
                    ))}
                    <div className="h-px bg-border/50 my-2"></div>
                    {/* Theme Toggle in Mobile Menu */}
                    <div className="flex items-center justify-between py-2">
                      <span className="text-lg font-medium text-foreground">تغییر تم</span>
                      <ThemeToggle />
                    </div>
                    <div className="h-px bg-border/50 my-2"></div>
                    <Button asChild variant="outline" className="w-full justify-center h-12 text-lg">
                      <Link href="/login">ورود به حساب</Link>
                    </Button>
                    <Button asChild className="w-full justify-center h-12 text-lg bg-primary text-primary-foreground">
                      <Link href="/login">شروع رایگان</Link>
                    </Button>
                  </nav>
                </SheetContent>
              </Sheet>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
