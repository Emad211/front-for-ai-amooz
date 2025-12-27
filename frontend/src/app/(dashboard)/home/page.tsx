
"use client";

import { Bell, BookOpen, Calendar, History, LogOut, Target, Clock, Video, FileText, ArrowLeft, GraduationCap } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { DashboardHeader as Header } from '@/components/layout/dashboard-header';
import Image from 'next/image';
import { StatCard } from '@/components/dashboard/ui/stat-card';
import { EventCard } from '@/components/dashboard/ui/event-card';
import { ActivityCard } from '@/components/dashboard/ui/activity-card';
import { DashboardHero } from '@/components/dashboard/dashboard-hero';


export default function StudentDashboard() {
  return (
    <div className="bg-background text-text-light min-h-screen">
      <Header />

      <main className="p-4 md:p-8 grid gap-8">
        <DashboardHero />
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          <StatCard title="پیشرفت دوره‌ها" value="۸ / ۵" subValue="دوره فعال" icon={<BookOpen className="text-primary"/>} />
          <StatCard title="درصد تکمیل" value="۷۵٪" subValue="میانگین کل" icon={<Target className="text-primary"/>} tag="ترم جاری" progress={75}/>
          <StatCard title="زمان مطالعه" value="۱۲:۳۰" subValue="ساعت مفید" icon={<Clock className="text-primary"/>} tag="این هفته" progress={60}/>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <Card className="lg:col-span-2 bg-card">
                <CardHeader className="flex-row items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-xl font-bold"><History className="text-primary"/> فعالیت‌های اخیر</CardTitle>
                    <Button variant="link" className="text-primary"><ArrowLeft className="h-4 w-4 mr-1"/> مشاهده همه</Button>
                </CardHeader>
                <CardContent className="space-y-4">
                   <ActivityCard title="ریاضیات گسسته - فصل ۲" time="۲ ساعت پیش" type="در حال انجام" icon={<FileText className="h-4 w-4 text-current"/>} />
                   <ActivityCard title="فیزیک کوانتوم - مقدمه" time="دیروز" type="ویدیو" icon={<Video className="h-4 w-4 text-current"/>} />
                   <ActivityCard title="زبان انگلیسی تخصصی" time="۳ روز پیش" type="آزمون" icon={<BookOpen className="h-4 w-4 text-current"/>} />
                </CardContent>
            </Card>
            
             <Card className="bg-card">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-xl font-bold"><Calendar className="text-primary"/> رویدادهای پیش رو</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <EventCard title="آزمون میان‌ترم ریاضی" status="ساعت ۱۰:۰۰ - آنلاین" date="۱۵" month="تیر" icon={<Clock className="h-3 w-3 text-current"/>}/>
                    <EventCard title="تحویل پروژه فیزیک" status="تا پایان روز" date="۲۰" month="تیر" icon={<FileText className="h-3 w-3 text-current"/>}/>
                    <Button variant="outline" className="w-full h-12 border-primary/50 text-primary/80 hover:bg-primary/10 hover:text-primary">مشاهده تقویم کامل</Button>
                </CardContent>
            </Card>
        </div>

      </main>
    </div>
  );
}
