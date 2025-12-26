'use client';

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';

export function LandingFooter() {
  return (
    <footer className="bg-card/30 border-t border-border/50">
      <div className="container mx-auto px-4 py-16">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12 md:gap-8">
          {/* Brand */}
          <div className="md:col-span-2">
            <Link href="/" className="flex items-center gap-3 mb-4">
              <span className="text-xl font-bold text-foreground whitespace-nowrap">AI-Amooz</span>
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
            </ul>
          </div>
          
          {/* Contact */}
          <div>
            <h4 className="font-semibold text-foreground mb-4">ارتباط با ما</h4>
            <ul className="space-y-3 text-sm">
              <li>
                <a href="mailto:info@ai-amooz.ir" className="text-muted-foreground hover:text-primary transition-colors">
                  info@ai-amooz.ir
                </a>
              </li>
              <li>
                <Link href="#" className="text-muted-foreground hover:text-primary transition-colors">
                  اینستاگرام
                </Link>
              </li>
              <li>
                <Link href="#" className="text-muted-foreground hover:text-primary transition-colors">
                  تلگرام
                </Link>
              </li>
            </ul>
          </div>
        </div>
        
        {/* Bottom */}
        <div className="mt-12 pt-8 border-t border-border/50">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
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
    </footer>
  );
}
