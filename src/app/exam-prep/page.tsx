'use client';

import { Header } from '@/components/layout/header';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Search, SlidersHorizontal, LayoutGrid, List, Play } from 'lucide-react';
import examsData from '@/lib/exams.json';
import Link from 'next/link';

const ExamCard = ({ exam }) => {
    const isInProgress = exam.tags.includes('ریاضیات') || exam.tags.includes('برنامه نویسی');
    return (
        <Card className="bg-card text-card-foreground overflow-hidden flex flex-col justify-between h-full rounded-2xl">
            <CardContent className="p-6">
                <div className="flex justify-start mb-4">
                    <Badge variant="secondary" className={`bg-opacity-20 text-sm font-normal ${
                        exam.tags[0] === 'هوش مصنوعی' ? 'bg-green-500/20 text-green-400 border-green-500/30' :
                        exam.tags[0] === 'ریاضیات' ? 'bg-purple-500/20 text-purple-400 border-purple-500/30' :
                        exam.tags[0] === 'فیزیک' ? 'bg-blue-500/20 text-blue-400 border-blue-500/30' :
                        exam.tags[0] === 'برنامه نویسی' ? 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30' :
                        exam.tags[0] === 'زبان' ? 'bg-pink-500/20 text-pink-400 border-pink-500/30' :
                        exam.tags[0] === 'آمار' ? 'bg-purple-500/20 text-purple-400 border-purple-500/30' :
                        'bg-gray-500/20 text-gray-400 border-gray-500/30'
                    } border`}>{exam.tags[0]}</Badge>
                </div>
                <h3 className="font-bold text-xl text-text-light mb-2">{exam.title}</h3>
                <p className="text-text-muted text-sm leading-relaxed mb-4">{exam.description}</p>
                <div className="flex items-center text-text-muted text-sm">
                    <List className="ml-2 h-4 w-4"/>
                    <span>{exam.questions} سوال</span>
                </div>
            </CardContent>
            <div className="px-6 pb-6">
                 {isInProgress ? (
                     <Button asChild className="w-full bg-primary hover:bg-primary/90 text-primary-foreground rounded-lg">
                        <Link href="#">ادامه یادگیری <Play className="mr-2 h-4 w-4 fill-current" /></Link>
                     </Button>
                 ) : (
                    <Button asChild variant="secondary" className="w-full bg-secondary hover:bg-secondary/80 text-secondary-foreground rounded-lg">
                        <Link href="#">
                            شروع یادگیری <Play className="h-4 w-4 mr-2 fill-current" />
                        </Link>
                    </Button>
                 )}
            </div>
        </Card>
    )
};


export default function ExamPrepPage() {
  return (
    <div className="bg-background text-text-light min-h-screen font-sans">
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
          
          <div className="mt-6 flex items-center gap-2 rounded-xl bg-card p-2">
                <span className="text-sm text-text-muted px-2">مرتب‌سازی:</span>
                <Button variant="ghost" className="bg-secondary text-primary flex-1">جدیدترین</Button>
                <Button variant="ghost" className="text-text-muted flex-1">محبوب</Button>
                <Button variant="ghost" className="text-text-muted flex-1">سخت‌ترین</Button>
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
