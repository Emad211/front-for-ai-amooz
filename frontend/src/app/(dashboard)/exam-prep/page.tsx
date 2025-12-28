
'use client';

import React from 'react';
import { DashboardHeader as Header } from '@/components/layout/dashboard-header';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Search, SlidersHorizontal, LayoutGrid, ArrowLeft } from 'lucide-react';
import { ExamCard } from '@/components/dashboard/ui/exam-card';
import { useExams } from '@/hooks/use-exams';
import { Skeleton } from '@/components/ui/skeleton';

export default function ExamPrepPage() {
  const { exams, isLoading, error, filters } = useExams();

  if (error) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <p className="text-destructive font-bold">{error}</p>
      </div>
    );
  }

  return (
    <main className="p-4 md:p-8 max-w-7xl mx-auto space-y-6 md:space-y-10">
      {/* Header Section */}
      <div className="flex flex-col gap-1 text-right">
        <h1 className="text-2xl md:text-4xl font-black text-foreground tracking-tight">آمادگی آزمون</h1>
        <p className="text-sm md:text-lg text-muted-foreground font-medium">دسترسی به بانک سوالات، آزمون‌های شبیه‌سازی شده و ارزیابی مهارت</p>
      </div>

      {/* Search & Filter Section */}
      <div className="sticky top-20 z-30 bg-background/80 backdrop-blur-xl py-2 -mx-4 px-4 md:static md:bg-transparent md:p-0 md:m-0 transition-all">
        <div className="flex flex-col md:flex-row gap-3 md:gap-4">
          <div className="relative flex-grow group">
            <Input
              type="search"
              placeholder="جستجوی آزمون، مبحث یا کلیدواژه..."
              value={filters.searchTerm}
              onChange={(e) => filters.setSearchTerm(e.target.value)}
              className="bg-card border-border/50 h-12 md:h-14 pl-12 pr-4 rounded-2xl focus:ring-primary/20 focus:border-primary transition-all shadow-sm group-hover:shadow-md"
            />
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
          </div>

          <div className="flex gap-2 overflow-x-auto pb-1 md:pb-0 no-scrollbar">
            <Button variant="outline" className="bg-card border-border/50 h-12 md:h-14 rounded-2xl whitespace-nowrap px-5 font-bold hover:bg-primary/5 hover:border-primary/30 transition-all shadow-sm">
              <SlidersHorizontal className="ml-2 h-4 w-4 text-primary" />
              فیلتر سطح
            </Button>
            <Button variant="outline" className="bg-card border-border/50 h-12 md:h-14 rounded-2xl whitespace-nowrap px-5 font-bold hover:bg-primary/5 hover:border-primary/30 transition-all shadow-sm">
              <LayoutGrid className="ml-2 h-4 w-4 text-primary" />
              موضوعات
            </Button>
          </div>
        </div>
      </div>
      
      {/* Quick Stats / Sort */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-primary/5 p-3 md:p-4 rounded-2xl border border-primary/10">
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
          <span className="text-xs md:text-sm text-muted-foreground font-bold whitespace-nowrap ml-2">مرتب‌سازی:</span>
          <Button variant="secondary" className="rounded-xl h-8 md:h-9 px-4 text-xs font-bold shadow-sm">جدیدترین</Button>
          <Button variant="ghost" className="rounded-xl h-8 md:h-9 px-4 text-xs font-bold text-muted-foreground hover:text-foreground">سخت‌ترین</Button>
        </div>
      </div>

      {/* Exams Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 md:gap-8">
        {isLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[250px] rounded-3xl" />
          ))
        ) : (
          exams.map((exam) => (
            <ExamCard key={exam.id} exam={exam} />
          ))
        )}
      </div>

      {/* Bottom CTA */}
      <div className="relative overflow-hidden bg-gradient-to-br from-primary to-primary/80 p-6 md:p-10 rounded-3xl text-primary-foreground shadow-2xl shadow-primary/20">
        <div className="relative z-10 flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="text-center md:text-right">
            <h2 className="text-xl md:text-3xl font-black mb-2">آزمون اختصاصی خودت رو بساز!</h2>
            <p className="text-sm md:text-lg opacity-90 font-medium">با انتخاب مباحث دلخواه، یک آزمون شبیه‌ساز شخصی‌سازی شده داشته باش.</p>
          </div>
          <Button size="lg" className="bg-white text-primary hover:bg-white/90 rounded-2xl font-black px-8 h-12 md:h-14 shadow-xl transition-all hover:scale-105">
            شروع ساخت آزمون
            <ArrowLeft className="mr-2 h-5 w-5" />
          </Button>
        </div>
        {/* Decorative circles */}
        <div className="absolute -top-10 -left-10 w-40 h-40 bg-white/10 rounded-full blur-3xl"></div>
        <div className="absolute -bottom-10 -right-10 w-40 h-40 bg-black/10 rounded-full blur-3xl"></div>
      </div>
    </main>
  );
}
