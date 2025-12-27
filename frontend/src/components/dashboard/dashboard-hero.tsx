'use client';

import { ArrowLeft } from 'lucide-react';
import { Button } from "@/components/ui/button";
import Image from 'next/image';

export const DashboardHero = () => {
  return (
    <div className="bg-gradient-to-br from-primary/10 via-card to-card p-4 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-4">
      <div className="text-right md:w-1/2 flex flex-col justify-center">
        <div className="inline-flex items-center gap-2 bg-primary/20 text-primary text-xs font-semibold px-3 py-1 rounded-full mb-4 self-start">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
          </span>
          AI دستیار شما
        </div>
        <h2 className="text-4xl font-extrabold mb-3 text-text-light">یادگیری را به سطح جدیدی ببرید</h2>
        <p className="text-text-light/80 text-base mb-6 max-w-md">
          AI-Amooz با تحلیل هوشمند، مسیر یادگیری شما را شخصی‌سازی می‌کند. بیایید درس بعدی را شروع کنیم.
        </p>
        <Button size="lg" className="bg-primary text-primary-foreground hover:bg-primary/90 flex-shrink-0 self-start">
          شروع یادگیری هوشمند
          <ArrowLeft className="mr-2 h-5 w-5" />
        </Button>
      </div>
      <div className="md:w-1/2 flex justify-center items-center">
        <Image src="/homee.png" alt="AI Learning" width={413} height={230} className="rounded-lg" priority />
      </div>
    </div>
  );
};
