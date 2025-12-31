'use client';

import { ReactNode } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { GraduationCap, UserRound } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { motion } from 'framer-motion';

export default function StartPage() {
  return (
    <div dir="rtl" className="min-h-screen bg-gradient-to-b from-background via-background/70 to-background flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-4xl space-y-10">
        <div className="text-center space-y-3">
          <p className="text-sm font-semibold text-primary">شروع رایگان</p>
          <h1 className="text-3xl md:text-4xl font-black text-foreground">مسیر خود را انتخاب کنید</h1>
          <p className="text-muted-foreground max-w-2xl mx-auto text-sm md:text-base">
            مشخص کنید به عنوان معلم می‌خواهید کلاس‌های خود را بسازید یا به عنوان دانش‌آموز با کد دعوت وارد می‌شوید.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <OptionCard
            title="معلم هستم"
            description="کلاس بسازید، دانش‌آموزان را مدیریت کنید و پیشرفت آن‌ها را ببینید."
            icon={<GraduationCap className="h-6 w-6" />}
            href="/teacher-signup"
            accent="bg-primary/10 text-primary border-primary/30"
          />
          <OptionCard
            title="دانش‌آموز هستم"
            description="با دریافت کد دعوت از معلم خود وارد کلاس شوید و درس‌ها را دنبال کنید."
            icon={<UserRound className="h-6 w-6" />}
            href="/join-code"
            accent="bg-emerald-500/10 text-emerald-700 border-emerald-200"
          />
        </div>

        <p className="text-center text-sm text-muted-foreground">
          اگر قبلاً حساب دارید، از بخش <Link href="/login" className="font-semibold text-primary hover:underline">ورود</Link> استفاده کنید.
        </p>
      </div>
    </div>
  );
}

function OptionCard({ title, description, icon, href, accent }: { title: string; description: string; icon: ReactNode; href: string; accent: string; }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <Card className="h-full border-border/70 shadow-sm hover:shadow-xl transition-all duration-300 hover:-translate-y-1 bg-card/70 backdrop-blur">
        <div className="p-6 space-y-6 flex flex-col h-full">
          <div className={`inline-flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-semibold ${accent}`}>
            {icon}
            <span>{title}</span>
          </div>
          <div className="space-y-3 flex-1">
            <h3 className="text-xl font-black text-foreground">{title}</h3>
            <p className="text-sm text-muted-foreground leading-7">{description}</p>
          </div>
          <Button asChild className="w-full h-12 text-base rounded-xl">
            <Link href={href}>ادامه</Link>
          </Button>
        </div>
      </Card>
    </motion.div>
  );
}
