
'use client';

import { DashboardHeader as Header } from '@/components/layout/dashboard-header';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Search, SlidersHorizontal, LayoutGrid, BookOpen } from 'lucide-react';
import { MOCK_COURSES } from '@/constants/mock';
import { CourseCard } from '@/components/dashboard/ui/course-card';

export default function ClassesPage() {
  return (
    <main className="p-4 md:p-8 max-w-7xl mx-auto space-y-6 md:space-y-10">
      {/* Header Section */}
      <div className="flex flex-col gap-1 text-right">
        <h1 className="text-2xl md:text-4xl font-black text-foreground tracking-tight">کلاس‌های من</h1>
        <p className="text-sm md:text-lg text-muted-foreground font-medium">مدیریت و مشاهده دوره‌های فعال و تکمیل شده</p>
      </div>

      {/* Search & Filter Section */}
      <div className="sticky top-20 z-30 bg-background/80 backdrop-blur-xl py-2 -mx-4 px-4 md:static md:bg-transparent md:p-0 md:m-0 transition-all">
        <div className="flex flex-col md:flex-row gap-3 md:gap-4">
          <div className="relative flex-grow group">
            <Input
              type="search"
              placeholder="جستجوی دوره، استاد یا مبحث..."
              className="bg-card border-border/50 h-12 md:h-14 pl-12 pr-4 rounded-2xl focus:ring-primary/20 focus:border-primary transition-all shadow-sm group-hover:shadow-md"
            />
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
          </div>

          <div className="flex gap-2 overflow-x-auto pb-1 md:pb-0 no-scrollbar">
            <Button variant="outline" className="bg-card border-border/50 h-12 md:h-14 rounded-2xl whitespace-nowrap px-5 font-bold hover:bg-primary/5 hover:border-primary/30 transition-all shadow-sm">
              <SlidersHorizontal className="ml-2 h-4 w-4 text-primary" />
              فیلتر پیشرفته
            </Button>
            <Button variant="outline" className="bg-card border-border/50 h-12 md:h-14 rounded-2xl whitespace-nowrap px-5 font-bold hover:bg-primary/5 hover:border-primary/30 transition-all shadow-sm">
              <LayoutGrid className="ml-2 h-4 w-4 text-primary" />
              دسته‌بندی
            </Button>
          </div>
        </div>
      </div>
      
      {/* Quick Stats / Sort */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-muted/30 p-3 md:p-4 rounded-2xl border border-border/50">
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
          <span className="text-xs md:text-sm text-muted-foreground font-bold whitespace-nowrap ml-2">مرتب‌سازی:</span>
          <Button variant="secondary" className="rounded-xl h-8 md:h-9 px-4 text-xs font-bold shadow-sm">جدیدترین</Button>
          <Button variant="ghost" className="rounded-xl h-8 md:h-9 px-4 text-xs font-bold text-muted-foreground hover:text-foreground">بیشترین پیشرفت</Button>
        </div>
      </div>

      {/* Courses Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 md:gap-8">
        {MOCK_COURSES.map((course) => (
            <CourseCard key={course.id} course={course} />
        ))}
      </div>

      {/* Empty State / Load More (Optional) */}
      <div className="flex flex-col items-center justify-center py-12 border-2 border-dashed border-border/50 rounded-3xl bg-muted/10">
        <div className="p-4 bg-background rounded-full shadow-xl mb-4">
          <BookOpen className="h-8 w-8 text-primary/40" />
        </div>
        <p className="text-muted-foreground font-bold">دوره‌های بیشتری برای نمایش وجود ندارد</p>
      </div>
    </main>
  );
}
