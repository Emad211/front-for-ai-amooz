
"use client";

import { Bell, BookOpen, Calendar, History, LogOut, Target, Clock, Video, FileText, ArrowLeft, GraduationCap } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Header } from '@/components/layout/header';
import Image from 'next/image';
import HomeImage from '@/assets/home.png';


const StatCard = ({ title, value, subValue, icon, tag, progress }) => (
  <Card className="bg-card text-text-light flex-1 min-w-[220px]">
    <CardHeader className="flex flex-row items-center justify-between pb-2 text-text-muted">
      <h3 className="text-sm font-medium">{title}</h3>
      {tag && <div className="text-xs font-semibold px-2 py-0.5 rounded-full border border-primary text-primary">{tag}</div>}
    </CardHeader>
    <CardContent>
      <div className="flex items-center gap-4">
        {icon && <div className="bg-primary/10 p-3 rounded-md">{icon}</div>}
        <div className="flex-grow">
          <p className="text-3xl font-bold">{value}</p>
          <p className="text-xs text-text-muted">{subValue}</p>
        </div>
      </div>
      {progress !== undefined && (
        <div className="mt-4">
          <Progress value={progress} className="h-2 [&>div]:bg-primary" />
        </div>
      )}
    </CardContent>
  </Card>
);

const EventCard = ({ title, status, icon, date, month }) => (
    <div className="flex items-center justify-between bg-card/50 p-4 rounded-lg hover:bg-border transition-colors cursor-pointer">
      <div className="flex items-center gap-4">
        <div className="flex flex-col items-center justify-center bg-primary/10 text-primary rounded-lg w-12 h-12 flex-shrink-0">
          <span className="text-sm font-bold">{date}</span>
          <span className="text-xs">{month}</span>
        </div>
        <div>
          <h4 className="font-semibold text-text-light">{title}</h4>
          <p className="text-xs text-text-muted flex items-center gap-1.5">
              {icon}
              <span>{status}</span>
          </p>
        </div>
      </div>
      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary">
          <ArrowLeft className="h-4 w-4"/>
      </div>
    </div>
  );
  
  const ActivityCard = ({ title, time, type, icon }) => (
    <div className="flex items-center justify-between bg-card/50 p-4 rounded-lg hover:bg-border transition-colors cursor-pointer">
      <div className="flex items-center gap-4">
         <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary">{icon}</div>
        <div>
          <h4 className="font-semibold text-text-light">{title}</h4>
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <span>{time}</span>
            <span className="text-primary">•</span>
            <span className="text-primary font-medium">{type}</span>
          </div>
        </div>
      </div>
      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary">
          <ArrowLeft className="h-4 w-4"/>
      </div>
    </div>
  );

export default function StudentDashboard() {
  return (
    <div className="bg-background text-text-light min-h-screen font-sans">
      <Header />

      <main className="p-4 md:p-8 grid gap-8">
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
                <Image src={HomeImage} alt="AI Learning" width={413} height={230} className="rounded-lg" priority />
            </div>
        </div>
        
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
                </CardContent>_
            </Card>
        </div>

      </main>
    </div>
  );
}
