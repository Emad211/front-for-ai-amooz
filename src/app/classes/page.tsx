'use client';

import { Header } from '@/components/layout/header';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Search, SlidersHorizontal, LayoutGrid, ArrowLeft, Play } from 'lucide-react';
import coursesData from '@/lib/courses.json';
import Link from 'next/link';

const CourseCard = ({ course }) => {
    const isFeatured = course.tags.includes('ریاضیات') || course.tags.includes('برنامه‌نویسی');
    return (
        <Card className="bg-card text-card-foreground overflow-hidden flex flex-col justify-between h-full">
            <CardContent className="p-6">
                <div className="flex justify-start mb-4">
                    {course.tags.map(tag => (
                        <Badge key={tag} variant="secondary" className={`bg-opacity-20 ${
                            tag === 'هوش مصنوعی' ? 'bg-green-500/20 text-green-400 border-green-500/30' :
                            tag === 'ریاضیات' ? 'bg-purple-500/20 text-purple-400 border-purple-500/30' :
                            tag === 'فیزیک' ? 'bg-blue-500/20 text-blue-400 border-blue-500/30' :
                            tag === 'برنامه‌نویسی' ? 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30' :
                            tag === 'زبان' ? 'bg-pink-500/20 text-pink-400 border-pink-500/30' :
                            tag === 'ادبیات' ? 'bg-purple-500/20 text-purple-400 border-purple-500/30' :
                            'bg-gray-500/20 text-gray-400 border-gray-500/30'
                        } border mr-2`}>{tag}</Badge>
                    ))}
                </div>
                <h3 className="font-bold text-xl text-text-light mb-2">{course.title}</h3>
                <p className="text-text-muted text-sm leading-relaxed">{course.description}</p>
            </CardContent>
            <div className="px-6 pb-6">
                 {isFeatured ? (
                     <Button asChild className="w-full bg-primary hover:bg-primary/90 text-primary-foreground">
                        <Link href="#">ادامه یادگیری <ArrowLeft className="mr-2 h-4 w-4" /></Link>
                     </Button>
                 ) : (
                    <Button asChild className="w-full bg-secondary hover:bg-secondary/80 text-primary">
                        <Link href="#">
                             شروع دوره <Play className="h-4 w-4 mr-2 fill-current" />
                        </Link>
                    </Button>
                 )}
            </div>
        </Card>
    )
};


export default function ClassesPage() {
  return (
    <div className="bg-background text-text-light min-h-screen font-sans">
      <Header />
      <main className="p-4 md:p-8">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-4xl font-bold text-text-light">کلاس‌های من</h1>
          <p className="text-text-muted mt-2">مدیریت و مشاهده دوره‌های فعال و تکمیل شده</p>

          <div className="mt-8 flex flex-col md:flex-row gap-4">
            <div className="relative flex-grow">
              <Input
                type="search"
                placeholder="جستجوی دوره، استاد یا مبحث..."
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
                <Button variant="ghost" className="text-text-muted">پیشرفت</Button>
          </div>

          <div className="mt-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {coursesData.courses.map((course) => (
                <CourseCard key={course.id} course={course} />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
