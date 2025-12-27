'use client';

import { ArrowLeft } from 'lucide-react';
import { Button } from "@/components/ui/button";
import Image from 'next/image';

export const DashboardHero = () => {
  return (
    <div className="relative overflow-hidden bg-gradient-to-br from-primary/20 via-card to-card p-6 md:p-10 rounded-3xl border border-primary/10 flex flex-col md:flex-row items-center justify-between gap-8 group">
      {/* Decorative background elements */}
      <div className="absolute -top-24 -left-24 w-64 h-64 bg-primary/10 rounded-full blur-3xl group-hover:bg-primary/20 transition-colors duration-700"></div>
      
      <div className="text-right md:w-3/5 flex flex-col justify-center relative z-10">
        <div className="inline-flex items-center gap-2 bg-primary/15 text-primary text-xs font-bold px-4 py-1.5 rounded-full mb-6 self-start border border-primary/20 shadow-sm shadow-primary/10">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
          </span>
          AI دستیار هوشمند شما
        </div>
        <h2 className="text-3xl md:text-5xl font-black mb-4 text-foreground leading-tight">
          یادگیری را به <span className="text-primary">سطح جدیدی</span> ببرید
        </h2>
        <p className="text-muted-foreground text-base md:text-lg mb-8 max-w-xl leading-relaxed">
          با تحلیل هوشمند AI-Amooz، مسیر یادگیری شما کاملاً شخصی‌سازی می‌شود. آماده‌اید درس بعدی را با هم شروع کنیم؟
        </p>
        <div className="flex flex-wrap gap-4 self-start">
          <Button size="lg" className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/20 h-12 px-8 rounded-xl transition-all hover:scale-105">
            شروع یادگیری هوشمند
            <ArrowLeft className="mr-2 h-5 w-5" />
          </Button>
        </div>
      </div>
      
      <div className="md:w-2/5 flex justify-center items-center relative z-10">
        <div className="relative">
          <div className="absolute -inset-4 bg-primary/20 rounded-full blur-2xl opacity-50"></div>
          <Image 
            src="/homee.png" 
            alt="AI Learning" 
            width={450} 
            height={250} 
            className="rounded-2xl relative z-10 drop-shadow-2xl transform group-hover:scale-105 transition-transform duration-500" 
            priority 
          />
        </div>
      </div>
    </div>
  );
};
