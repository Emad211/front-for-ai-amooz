'use client';

import { Button } from '@/components/ui/button';
import { ArrowLeft, Play, Sparkles } from 'lucide-react';
import Link from 'next/link';
import Image from 'next/image';

interface HeroSectionProps {
  heroImage: {
    imageUrl: string;
    description: string;
  };
}

export const HeroSection = ({ heroImage }: HeroSectionProps) => (
  <section className="relative min-h-screen flex items-center justify-center overflow-hidden py-20 md:py-0 bg-background">
    {/* Subtle Background */}
    <div className="absolute top-0 right-0 w-1/2 h-1/2 bg-primary/5 rounded-full blur-[120px]"></div>

    <div className="container mx-auto px-4 pt-20 md:pt-24 pb-12 relative z-10">
      <div className="max-w-4xl mx-auto text-center">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1.5 md:px-4 md:py-2 rounded-full bg-primary/10 border border-primary/20 mb-6 md:mb-8">
          <Sparkles className="w-3.5 h-3.5 md:w-4 md:h-4 text-primary" />
          <span className="text-xs md:text-sm font-medium text-primary">پلتفرم آموزشی نسل جدید</span>
        </div>

        <h1 className="text-3xl sm:text-4xl md:text-6xl lg:text-7xl font-black tracking-tight mb-6 leading-[1.2]">
          <span className="text-foreground">یادگیری هوشمند</span>
          <br />
          <span className="bg-gradient-to-l from-primary via-primary to-primary/70 text-transparent bg-clip-text">
            با قدرت AI
          </span>
        </h1>

        <p className="text-base md:text-xl text-muted-foreground max-w-2xl mx-auto mb-8 md:mb-10 leading-relaxed px-4">
          دستیار هوشمند شخصی شما برای تسلط بر هر مبحثی. مسیر یادگیری اختصاصی، پاسخ‌گویی ۲۴ ساعته و آزمون‌های تطبیقی.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-12 md:mb-16 px-6 sm:px-0">
          <Button
            asChild
            size="lg"
            className="w-full sm:w-auto h-12 md:h-14 px-8 text-base md:text-lg bg-primary text-primary-foreground hover:bg-primary/90 shadow-xl shadow-primary/25 transition-all hover:scale-105"
          >
            <Link href="/login">
              شروع رایگان
              <ArrowLeft className="mr-2 h-5 w-5" />
            </Link>
          </Button>
          <Button
            asChild
            variant="outline"
            size="lg"
            className="w-full sm:w-auto h-12 md:h-14 px-8 text-base md:text-lg border-border/50 hover:bg-card/50"
          >
            <Link href="#features">
              <Play className="ml-2 h-4 w-4" />
              مشاهده دمو
            </Link>
          </Button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:flex items-center justify-center gap-6 md:gap-16 text-center">
          <div className="col-span-1">
            <div className="text-2xl md:text-4xl font-bold text-foreground">۵۰۰۰+</div>
            <div className="text-xs md:text-sm text-muted-foreground mt-1">دانش‌آموز فعال</div>
          </div>
          <div className="w-px h-12 bg-border hidden md:block"></div>
          <div className="col-span-1">
            <div className="text-2xl md:text-4xl font-bold text-foreground">۹۸٪</div>
            <div className="text-xs md:text-sm text-muted-foreground mt-1">رضایت کاربران</div>
          </div>
          <div className="w-px h-12 bg-border hidden md:block"></div>
          <div className="col-span-2 md:col-span-1">
            <div className="text-2xl md:text-4xl font-bold text-foreground">۲۴/۷</div>
            <div className="text-xs md:text-sm text-muted-foreground mt-1">پشتیبانی هوشمند</div>
          </div>
        </div>
      </div>

      {/* Hero Image */}
      {heroImage && (
        <div className="mt-16 md:mt-20 max-w-6xl mx-auto px-2 md:px-0">
          <div className="relative group">
            <div className="absolute -inset-1 bg-gradient-to-r from-primary/20 via-primary/10 to-primary/20 rounded-3xl blur-xl opacity-50 group-hover:opacity-75 transition-opacity"></div>
            <div className="relative rounded-xl md:rounded-2xl border border-border/50 bg-card/80 backdrop-blur-sm p-1.5 md:p-2 shadow-2xl">
              <div className="absolute top-3 left-3 md:top-4 md:left-4 flex gap-1.5 md:gap-2 z-10">
                <span className="w-2 h-2 md:w-3 md:h-3 rounded-full bg-red-500"></span>
                <span className="w-2 h-2 md:w-3 md:h-3 rounded-full bg-yellow-500"></span>
                <span className="w-2 h-2 md:w-3 md:h-3 rounded-full bg-green-500"></span>
              </div>
              <Image
                src={heroImage.imageUrl}
                alt={heroImage.description}
                width={1400}
                height={900}
                className="rounded-lg md:rounded-xl"
                priority
              />
            </div>
          </div>
        </div>
      )}
    </div>
  </section>
);
