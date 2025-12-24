
"use client";

import Image from 'next/image';
import { Bell, BookOpen, Calendar, History, LogOut, Target, Clock, Video, FileText, ArrowLeft } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

const StatCard = ({ title, value, subValue, icon, tag, progress, fullWidth = false }) => (
  <Card className={`bg-card text-text-light flex-1 ${fullWidth ? 'min-w-full' : 'min-w-[220px]'}`}>
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
  <div className="flex items-center justify-between bg-card p-4 rounded-lg hover:bg-border transition-colors cursor-pointer">
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
  <div className="flex items-center justify-between bg-card p-4 rounded-lg hover:bg-border transition-colors cursor-pointer">
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
      <header className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-8">
            <Image
              src="https://picsum.photos/seed/logo/120/32"
              width={120}
              height={32}
              alt="AI-Amooz Logo"
            />
        </div>
        
        <nav className="hidden md:flex items-center gap-1 bg-card p-1 rounded-full">
            <Button variant="ghost" className="bg-primary text-primary-foreground rounded-full">داشبورد</Button>
            <Button variant="ghost" className="text-text-muted rounded-full">کلاس‌ها</Button>
            <Button variant="ghost" className="text-text-muted rounded-full">آمادگی آزمون</Button>
        </nav>

        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" className="relative text-text-muted">
            <Bell className="h-5 w-5" />
             <span className="absolute top-1.5 right-1.5 flex h-2 w-2">
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
            </span>
          </Button>
          <div className="flex items-center gap-3">
            <Avatar className="border-2 border-primary">
              <AvatarImage src="https://picsum.photos/seed/user/40/40" alt="Ali Rezaei" />
              <AvatarFallback>AR</AvatarFallback>
            </Avatar>
             <div className="text-right hidden sm:block">
              <p className="font-semibold text-sm text-text-light">علی رضایی</p>
              <p className="text-xs text-text-muted">دانش آموز ممتاز</p>
            </div>
          </div>
           <Button variant="ghost" size="icon" className="text-text-muted">
             <LogOut className="h-5 w-5" />
           </Button>
        </div>
      </header>

      <main className="p-4 md:p-8 grid gap-8">
        <div style={{backgroundColor: '#103E33'}} className="p-8 rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="text-right">
            <div className="inline-flex items-center gap-2 bg-primary/20 text-primary text-xs font-semibold px-3 py-1 rounded-full mb-4">
                <span className="relative flex h-2 w-2">
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                </span>
              هوش مصنوعی فعال است
            </div>
            <h2 className="text-3xl font-bold mb-2 text-text-light">👋 خوش آمدید به AI-Amooz</h2>
            <p className="text-text-light/80 max-w-lg">
              مسیر یادگیری شما با هوش مصنوعی بهینه سازی شده است. آماده ادامه فیزیک کوانتوم هستید؟
            </p>
          </div>
          <Button size="lg" className="bg-primary text-primary-foreground hover:bg-primary/90 flex-shrink-0 self-start md:self-center mt-4 md:mt-0">
            ادامه یادگیری هوشمند
            <ArrowLeft className="mr-2 h-5 w-5" />
          </Button>
        </div>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          <StatCard title="پیشرفت دوره‌ها" value="۸ / ۵" subValue="دوره فعال" icon={<BookOpen className="text-primary"/>} />
          <StatCard title="درصد تکمیل" value="۷۵٪" subValue="میانگین کل" icon={<Target className="text-primary"/>} tag="ترم جاری" progress={75}/>
          <StatCard title="زمان مطالعه" value="۱۲:۳۰" subValue="ساعت مفید" icon={<Clock className="text-primary"/>} tag="این هفته" progress={60}/>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <section className="lg:col-span-2">
                 <div className="flex items-center justify-between mb-4">
                    <h3 className="flex items-center gap-2 text-xl font-bold"><History className="text-primary"/> فعالیت‌های اخیر</h3>
                    <Button variant="link" className="text-primary"><ArrowLeft className="h-4 w-4 mr-1"/> مشاهده همه</Button>
                </div>
                <div className="space-y-4">
                   <ActivityCard title="ریاضیات گسسته - فصل ۲" time="۲ ساعت پیش" type="در حال انجام" icon={<FileText className="h-4 w-4 text-current"/>} />
                   <ActivityCard title="فیزیک کوانتوم - مقدمه" time="دیروز" type="ویدیو" icon={<Video className="h-4 w-4 text-current"/>} />
                   <ActivityCard title="زبان انگلیسی تخصصی" time="۳ روز پیش" type="آزمون" icon={<BookOpen className="h-4 w-4 text-current"/>} />
                </div>
            </section>
            
             <section>
                <div className="flex items-center justify-between mb-4">
                    <h3 className="flex items-center gap-2 text-xl font-bold"><Calendar className="text-primary"/> رویدادهای پیش رو</h3>
                </div>
                <div className="space-y-4">
                    <EventCard title="آزمون میان‌ترم ریاضی" status="ساعت ۱۰:۰۰ - آنلاین" date="۱۵" month="تیر" icon={<Clock className="h-3 w-3 text-current"/>}/>
                    <EventCard title="تحویل پروژه فیزیک" status="تا پایان روز" date="۲۰" month="تیر" icon={<FileText className="h-3 w-3 text-current"/>}/>
                    <Button variant="outline" className="w-full h-12 border-primary text-primary hover:bg-primary/10 hover:text-primary">مشاهده تقویم کامل</Button>
                </div>
            </section>
        </div>

      </main>
    </div>
  );
}
