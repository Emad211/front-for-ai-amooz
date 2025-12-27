'use client';

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Instagram, Send, Mail } from 'lucide-react';

export function LandingFooter() {
  return (
    <footer className="bg-muted/90 dark:bg-card/90">
      <div className="container mx-auto px-4 py-12 md:py-16">
        {/* Mobile Footer */}
        <div className="md:hidden">
          {/* Brand - Centered on Mobile */}
          <div className="text-center mb-8">
            <Link href="/" className="inline-flex items-center gap-2 mb-4 group relative">
              <div className="relative h-12 w-16">
                <Image
                  src="/logo (2).png"
                  alt="AI-Amooz logo"
                  fill
                  sizes="128px"
                  className="object-contain transition-all duration-300 scale-[2.2] origin-center"
                  priority
                />
              </div>
              <span className="text-2xl font-bold text-foreground whitespace-nowrap tracking-tighter ml-2">AI-Amooz</span>
            </Link>
            <p className="text-muted-foreground text-sm max-w-xs mx-auto leading-relaxed">
              پلتفرم آموزشی هوشمند با کمک هوش مصنوعی
            </p>
          </div>

          {/* Social Links - Mobile */}
          <div className="flex justify-center gap-4 mb-8">
            <a href="mailto:info@ai-amooz.ir" className="w-12 h-12 rounded-full bg-background border border-border flex items-center justify-center text-muted-foreground hover:text-primary hover:border-primary transition-colors">
              <Mail className="w-5 h-5" />
            </a>
            <Link href="#" className="w-12 h-12 rounded-full bg-background border border-border flex items-center justify-center text-muted-foreground hover:text-primary hover:border-primary transition-colors">
              <Instagram className="w-5 h-5" />
            </Link>
            <Link href="#" className="w-12 h-12 rounded-full bg-background border border-border flex items-center justify-center text-muted-foreground hover:text-primary hover:border-primary transition-colors">
              <Send className="w-5 h-5" />
            </Link>
          </div>

          {/* Quick Links - Mobile Grid */}
          <div className="grid grid-cols-2 gap-4 text-center mb-8">
            <Link href="#features" className="py-3 px-4 rounded-xl bg-background border border-border text-sm text-muted-foreground hover:text-primary hover:border-primary transition-colors">
              ویژگی‌ها
            </Link>
            <Link href="#how-it-works" className="py-3 px-4 rounded-xl bg-background border border-border text-sm text-muted-foreground hover:text-primary hover:border-primary transition-colors">
              نحوه کار
            </Link>
            <Link href="#faq" className="py-3 px-4 rounded-xl bg-background border border-border text-sm text-muted-foreground hover:text-primary hover:border-primary transition-colors">
              سوالات متداول
            </Link>
            <Link href="/admin-login" className="py-3 px-4 rounded-xl bg-primary/10 border border-primary text-sm text-primary hover:bg-primary/20 hover:border-primary transition-colors">
              پنل مدیریت
            </Link>
          </div>

          {/* Copyright - Mobile */}
          <div className="text-center pt-6 border-t border-border">
            <p className="text-xs text-muted-foreground">
              &copy; {new Date().getFullYear()} AI-Amooz. تمام حقوق محفوظ است.
            </p>
          </div>
        </div>

        {/* Desktop Footer */}
        <div className="hidden md:block">
          <div className="grid grid-cols-4 gap-8">
            {/* Brand */}
            <div className="col-span-2">
              <Link href="/" className="flex items-center gap-2 mb-6 group relative">
                <div className="relative h-12 w-16">
                  <Image
                    src="/logo (2).png"
                    alt="AI-Amooz logo"
                    fill
                    sizes="128px"
                    className="object-contain transition-all duration-300 scale-[2.2] origin-center"
                    priority
                  />
                </div>
                <span className="text-2xl font-bold text-foreground whitespace-nowrap tracking-tighter ml-2">AI-Amooz</span>
              </Link>
              <p className="text-muted-foreground max-w-sm leading-relaxed">
                پلتفرم آموزشی هوشمند که با کمک هوش مصنوعی، یادگیری را برای شما شخصی‌سازی می‌کند.
              </p>
            </div>
            
            {/* Links */}
            <div>
              <h4 className="font-semibold text-foreground mb-4">لینک‌های سریع</h4>
              <ul className="space-y-3 text-sm">
                <li>
                  <Link href="#features" className="text-muted-foreground hover:text-primary transition-colors">
                    ویژگی‌ها
                  </Link>
                </li>
                <li>
                  <Link href="#how-it-works" className="text-muted-foreground hover:text-primary transition-colors">
                    نحوه کار
                  </Link>
                </li>
                <li>
                  <Link href="#faq" className="text-muted-foreground hover:text-primary transition-colors">
                    سوالات متداول
                  </Link>
                </li>
                <li>
                  <Link href="/admin-login" className="text-primary font-medium hover:text-primary/80 transition-colors">
                    پنل مدیریت
                  </Link>
                </li>
              </ul>
            </div>
            
            {/* Contact */}
            <div>
              <h4 className="font-semibold text-foreground mb-4">ارتباط با ما</h4>
              <ul className="space-y-3 text-sm">
                <li>
                  <a href="mailto:info@ai-amooz.ir" className="text-muted-foreground hover:text-primary transition-colors flex items-center gap-2">
                    <Mail className="w-4 h-4" />
                    info@ai-amooz.ir
                  </a>
                </li>
                <li>
                  <Link href="#" className="text-muted-foreground hover:text-primary transition-colors flex items-center gap-2">
                    <Instagram className="w-4 h-4" />
                    اینستاگرام
                  </Link>
                </li>
                <li>
                  <Link href="#" className="text-muted-foreground hover:text-primary transition-colors flex items-center gap-2">
                    <Send className="w-4 h-4" />
                    تلگرام
                  </Link>
                </li>
              </ul>
            </div>
          </div>
          
          {/* Bottom */}
          <div className="mt-12 pt-8 border-t border-border">
            <div className="flex justify-between items-center">
              <p className="text-sm text-muted-foreground">
                &copy; {new Date().getFullYear()} AI-Amooz. تمام حقوق محفوظ است.
              </p>
              <div className="flex gap-6 text-sm">
                <Link href="#" className="text-muted-foreground hover:text-primary transition-colors">
                  حریم خصوصی
                </Link>
                <Link href="#" className="text-muted-foreground hover:text-primary transition-colors">
                  قوانین استفاده
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
