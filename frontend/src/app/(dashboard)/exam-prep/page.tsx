
'use client';

import { DashboardHeader as Header } from '@/components/layout/dashboard-header';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Search, SlidersHorizontal, LayoutGrid, List, Play, ArrowLeft } from 'lucide-react';
import examsData from '@/lib/exams.json';
import Link from 'next/link';
import { ExamCard } from '@/components/dashboard/ui/exam-card';

export default function ExamPrepPage() {
  return (
    <div className="bg-background text-text-light min-h-screen">
      <Header />
      <main className="p-4 md:p-8">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-4xl font-bold text-text-light">آمادگی آزمون</h1>
          <p className="text-text-muted mt-2">دسترسی به بانک سوالات، آزمون‌های شبیه‌سازی شده و ارزیابی مهارت</p>

          <div className="mt-8 flex flex-col md:flex-row gap-4">
            <div className="relative flex-grow">
              <Input
                type="search"
                placeholder="جستجوی آزمون، مبحث یا کلیدواژه..."
                className="bg-card border-border h-12 pl-12 pr-4 rounded-lg focus:ring-primary focus:border-primary"
              />
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-text-muted" />
            </div>

            <div className="flex gap-4">
              <Button variant="outline" className="bg-card border-border h-12">
                <SlidersHorizontal className="ml-2 h-4 w-4" />
                همه سطوح
              </Button>
              <Button variant="outline" className="bg-card border-border h-12">
                <LayoutGrid className="ml-2 h-4 w-4" />
                همه موضوعات
              </Button>
            </div>
          </div>
          
          <div className="mt-6 flex items-center gap-4">
            <span className="text-sm text-text-muted">مرتب‌سازی:</span>
            <Button variant="ghost" className="bg-card text-text-light">جدیدترین</Button>
            <Button variant="ghost" className="text-text-muted">محبوب</Button>
            <Button variant="ghost" className="text-text-muted">سخت‌ترین</Button>
          </div>

          <div className="mt-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {examsData.exams.map((exam) => (
                <ExamCard key={exam.id} exam={exam} />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
