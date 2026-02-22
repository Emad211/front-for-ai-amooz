'use client';

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Instagram, Send, Mail, Heart, ArrowUp } from 'lucide-react';
import { SITE_CONFIG } from '@/constants/site';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';

export function LandingFooter() {
  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <footer className="relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 bg-gradient-to-b from-background via-muted/80 to-muted" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom,rgba(var(--primary-rgb),0.05),transparent_70%)]" />
      
      <div className="container mx-auto px-4 py-16 md:py-20 relative z-10">
        {/* Mobile Footer */}
        <div className="md:hidden">
          {/* Brand - Centered on Mobile */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-8"
          >
            <Link href="/" className="inline-flex items-center gap-2 mb-4 group relative">
              <div className="relative h-12 w-16">
                <Image
                  src="/logo.png"
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
              یادگیری سفری است که از کلاس درس آغاز می‌شود؛ و ما همسفر توایم
            </p>
          </motion.div>

          {/* Social Links - Mobile */}
          <div className="flex justify-center gap-3 mb-8">
            {[
              { href: `mailto:${SITE_CONFIG.links.email}`, icon: Mail, label: 'Email' },
              { href: SITE_CONFIG.links.instagram, icon: Instagram, label: 'Instagram' },
              { href: SITE_CONFIG.links.telegram, icon: Send, label: 'Telegram' },
            ].map((social, index) => (
              <motion.a
                key={social.label}
                href={social.href}
                initial={{ opacity: 0, scale: 0.8 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                whileHover={{ scale: 1.1, y: -2 }}
                className="w-12 h-12 rounded-2xl bg-card/80 border border-border/50 flex items-center justify-center text-muted-foreground hover:text-primary hover:border-primary/50 hover:bg-primary/5 transition-all duration-300"
              >
                <social.icon className="w-5 h-5" />
              </motion.a>
            ))}
          </div>

          {/* Quick Links - Mobile Grid */}
          <div className="grid grid-cols-2 gap-3 text-center mb-8">
            {[
              { href: '#features', label: 'ویژگی‌ها' },
              { href: '#how-it-works', label: 'نحوه کار' },
              { href: '#faq', label: 'سوالات متداول' },
              { href: '/admin-login', label: 'پنل مدیریت', highlight: true },
            ].map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`py-3 px-4 rounded-xl border text-sm transition-all duration-300 ${
                  link.highlight
                    ? 'bg-primary/10 border-primary/30 text-primary hover:bg-primary/20'
                    : 'bg-card/50 border-border/50 text-muted-foreground hover:text-primary hover:border-primary/30'
                }`}
              >
                {link.label}
              </Link>
            ))}
          </div>

          {/* Copyright - Mobile */}
          <div className="text-center pt-6 border-t border-border/50">
            <p className="text-xs text-muted-foreground flex items-center justify-center gap-1">
              ساخته شده با <Heart className="w-3 h-3 text-red-500 fill-red-500" /> در ایران
            </p>
            <p className="text-xs text-muted-foreground mt-2">
              &copy; {new Date().getFullYear()} AI-Amooz. تمام حقوق محفوظ است.
            </p>
          </div>
        </div>

        {/* Desktop Footer */}
        <div className="hidden md:block">
          <div className="grid grid-cols-12 gap-8">
            {/* Brand */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="col-span-5"
            >
              <Link href="/" className="flex items-center gap-2 mb-6 group relative">
                <div className="relative h-14 w-18">
                  <Image
                    src="/logo.png"
                    alt="AI-Amooz logo"
                    fill
                    sizes="128px"
                    className="object-contain transition-all duration-300 scale-[2.2] origin-center"
                    priority
                  />
                </div>
                <span className="text-3xl font-black text-foreground whitespace-nowrap tracking-tighter ml-2">AI-Amooz</span>
              </Link>
              <p className="text-muted-foreground max-w-md leading-relaxed text-base mb-6">
                یادگیری سفری است که از کلاس درس آغاز می‌شود؛ و ما همسفر توایم. در این سفر، مسیر یادگیری‌ات هرگز به بن‌بست نمی‌رسد.
              </p>
              
              {/* Social Links */}
              <div className="flex gap-3">
                {[
                  { href: `mailto:${SITE_CONFIG.links.email}`, icon: Mail, label: 'Email' },
                  { href: SITE_CONFIG.links.instagram, icon: Instagram, label: 'Instagram' },
                  { href: SITE_CONFIG.links.telegram, icon: Send, label: 'Telegram' },
                ].map((social, index) => (
                  <motion.a
                    key={social.label}
                    href={social.href}
                    initial={{ opacity: 0, scale: 0.8 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: index * 0.1 }}
                    whileHover={{ scale: 1.1, y: -3 }}
                    className="w-11 h-11 rounded-xl bg-card/80 border border-border/50 flex items-center justify-center text-muted-foreground hover:text-primary hover:border-primary/50 hover:bg-primary/5 transition-all duration-300"
                  >
                    <social.icon className="w-5 h-5" />
                  </motion.a>
                ))}
              </div>
            </motion.div>
            
            {/* Links */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
              className="col-span-3"
            >
              <h4 className="font-bold text-foreground mb-5 text-lg">لینک‌های سریع</h4>
              <ul className="space-y-3">
                {[
                  { href: '#features', label: 'ویژگی‌ها' },
                  { href: '#how-it-works', label: 'نحوه کار' },
                  { href: '#faq', label: 'سوالات متداول' },
                  { href: '/admin-login', label: 'پنل مدیریت', highlight: true },
                ].map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className={`text-sm transition-colors hover:translate-x-1 inline-block ${
                        link.highlight ? 'text-primary font-medium' : 'text-muted-foreground hover:text-primary'
                      }`}
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </motion.div>
            
            {/* Contact */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.2 }}
              className="col-span-4"
            >
              <h4 className="font-bold text-foreground mb-5 text-lg">ارتباط با ما</h4>
              <ul className="space-y-3">
                <li>
                  <a href={`mailto:${SITE_CONFIG.links.email}`} className="text-sm text-muted-foreground hover:text-primary transition-colors flex items-center gap-2">
                    <Mail className="w-4 h-4" />
                    {SITE_CONFIG.links.email}
                  </a>
                </li>
                <li>
                  <Link href={SITE_CONFIG.links.instagram} className="text-sm text-muted-foreground hover:text-primary transition-colors flex items-center gap-2">
                    <Instagram className="w-4 h-4" />
                    اینستاگرام
                  </Link>
                </li>
                <li>
                  <Link href={SITE_CONFIG.links.telegram} className="text-sm text-muted-foreground hover:text-primary transition-colors flex items-center gap-2">
                    <Send className="w-4 h-4" />
                    تلگرام
                  </Link>
                </li>
              </ul>
            </motion.div>
          </div>
          
          {/* Bottom */}
          <div className="mt-12 pt-8 border-t border-border/50">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-4">
                <p className="text-sm text-muted-foreground">
                  &copy; {new Date().getFullYear()} AI-Amooz. تمام حقوق محفوظ است.
                </p>
                <span className="text-muted-foreground/30">|</span>
                <p className="text-sm text-muted-foreground flex items-center gap-1">
                  ساخته شده با <Heart className="w-3.5 h-3.5 text-red-500 fill-red-500" /> در ایران
                </p>
              </div>
              <div className="flex items-center gap-6">
                <div className="flex gap-6 text-sm">
                  <Link href="#" className="text-muted-foreground hover:text-primary transition-colors">
                    حریم خصوصی
                  </Link>
                  <Link href="#" className="text-muted-foreground hover:text-primary transition-colors">
                    قوانین استفاده
                  </Link>
                </div>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={scrollToTop}
                  className="w-10 h-10 rounded-xl border-border/50 hover:border-primary/50 hover:bg-primary/5"
                >
                  <ArrowUp className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
