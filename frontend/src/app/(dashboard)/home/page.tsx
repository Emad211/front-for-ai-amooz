
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
import { MobileNav } from '@/components/layout/mobile-nav';


export default function StudentDashboard() {
  return (
    <main className="p-4 md:p-8 max-w-7xl mx-auto space-y-8 md:space-y-10">
      {/* Welcome Section */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div className="text-right">
          <h1 className="text-2xl md:text-3xl font-black text-foreground">داشبورد من</h1>
          <p className="text-sm md:text-base text-muted-foreground mt-1 font-medium">خوش آمدی علیرضا! بیا امروز هم چیزهای جدید یاد بگیریم.</p>
        </div>
        <div className="hidden md:block text-sm font-bold text-muted-foreground bg-muted/50 px-4 py-2 rounded-xl border border-border/50">
          امروز: ۷ تیر ۱۴۰۳
        </div>
      </div>

      <DashboardHero />
      
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
        <StatCard 
          title="پیشرفت دوره‌ها" 
          value="۵ / ۸" 
          subValue="دوره فعال در این ترم" 
          icon={<BookOpen className="h-5 w-5 md:h-6 md:w-6"/>} 
          progress={62}
        />
        <StatCard 
          title="درصد تکمیل" 
          value="۷۵٪" 
          subValue="میانگین نمرات کل" 
          icon={<Target className="h-5 w-5 md:h-6 md:w-6"/>} 
          tag="ترم جاری" 
          progress={75}
        />
        <StatCard 
          title="زمان مطالعه" 
          value="۱۲:۳۰" 
          subValue="ساعت مطالعه مفید" 
          icon={<Clock className="h-5 w-5 md:h-6 md:w-6"/>} 
          tag="این هفته" 
          progress={60}
        />
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 md:gap-8">
          <Card className="lg:col-span-2 bg-card border-border/50 rounded-2xl md:rounded-3xl overflow-hidden">
              <CardHeader className="flex flex-row items-center justify-between border-b border-border/50 bg-muted/20 px-4 md:px-6 py-3 md:py-4">
                  <CardTitle className="flex items-center gap-2 md:gap-3 text-lg md:text-xl font-black">
                    <div className="p-1.5 md:p-2 bg-primary/10 rounded-lg">
                      <History className="h-4 w-4 md:h-5 md:w-5 text-primary"/>
                    </div>
                    فعالیت‌های اخیر
                  </CardTitle>
                  <Button variant="ghost" size="sm" className="text-primary text-xs md:text-sm font-bold hover:bg-primary/10 rounded-xl h-8 md:h-10">
                    مشاهده همه
                    <ArrowLeft className="mr-1 md:mr-2 h-3 w-3 md:h-4 md:w-4"/>
                  </Button>
              </CardHeader>
              <CardContent className="p-4 md:p-6 space-y-3 md:space-y-4">
                 <ActivityCard title="ریاضیات گسسته - فصل ۲" time="۲ ساعت پیش" type="در حال انجام" icon={<FileText className="h-4 w-4 md:h-5 md:w-5"/>} />
                 <ActivityCard title="فیزیک کوانتوم - مقدمه" time="دیروز" type="ویدیو" icon={<Video className="h-4 w-4 md:h-5 md:w-5"/>} />
                 <ActivityCard title="زبان انگلیسی تخصصی" time="۳ روز پیش" type="آزمون" icon={<BookOpen className="h-4 w-4 md:h-5 md:w-5"/>} />
              </CardContent>
          </Card>
          
           <Card className="bg-card border-border/50 rounded-2xl md:rounded-3xl overflow-hidden">
              <CardHeader className="border-b border-border/50 bg-muted/20 px-4 md:px-6 py-3 md:py-4">
                  <CardTitle className="flex items-center gap-2 md:gap-3 text-lg md:text-xl font-black">
                    <div className="p-1.5 md:p-2 bg-primary/10 rounded-lg">
                      <Calendar className="h-4 w-4 md:h-5 md:w-5 text-primary"/>
                    </div>
                    رویدادهای پیش رو
                  </CardTitle>
              </CardHeader>
              <CardContent className="p-4 md:p-6 space-y-3 md:space-y-4">
                  <EventCard title="آزمون میان‌ترم ریاضی" status="ساعت ۱۰:۰۰ - آنلاین" date="۱۵" month="تیر" icon={<Clock className="h-3 w-3 md:h-4 md:w-4"/>}/>
                  <EventCard title="تحویل پروژه فیزیک" status="تا پایان روز" date="۲۰" month="تیر" icon={<FileText className="h-3 w-3 md:h-4 md:w-4"/>}/>
                  <Button variant="outline" className="w-full h-10 md:h-12 border-primary/30 text-primary text-xs md:text-sm font-bold hover:bg-primary/10 hover:border-primary rounded-xl md:rounded-2xl mt-2 transition-all">
                    مشاهده تقویم کامل
                  </Button>
              </CardContent>
          </Card>
      </div>
    </main>
  );
}
