
"use client";

import Image from 'next/image';
import { Bell, BookOpen, Calendar, History, LogOut, Target, Clock, Video, FileText, ArrowLeft } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

const Logo = () => (
    <svg width="120" height="32" viewBox="0 0 100 30" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M53.1329 13.0416C54.0202 10.9232 53.0335 8.40645 50.9151 7.51916C48.7967 6.63188 46.28 7.6186 45.3927 9.73699C44.5054 11.8554 45.4921 14.3721 47.6105 15.2594C49.7289 16.1467 52.2456 15.1599 53.1329 13.0416Z" fill="#34D399"/>
        <path d="M49.4975 12.3582C49.7999 12.483 50.129 12.5454 50.4581 12.5454C50.9151 12.5454 51.3721 12.383 51.7584 12.069C52.1287 11.755 52.3739 11.3161 52.4431 10.8454C52.5122 10.3747 52.3847 9.89539 52.0913 9.49964C51.798 9.1039 51.3636 8.81669 50.8659 8.69191L49.4975 12.3582Z" fill="#F9FAFB"/>
        <path d="M49.2319 23.4998C49.2319 23.4998 55.4361 23.1116 55.6921 18.2361C55.948 13.3606 48.9136 12.193 48.9136 12.193" stroke="#34D399" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M43.9551 23.5002C43.9551 23.5002 37.7508 23.1119 37.4949 18.2364C37.239 13.3609 44.2733 12.1933 44.2733 12.1933" stroke="#34D399" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M44.2733 12.1934L48.9136 12.1934" stroke="#34D399" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <text fill="#F9FAFB" fontFamily="sans-serif" fontSize="6" x="35" y="29">AI-Amooz</text>
    </svg>
);


export default function StudentDashboard() {
  return (
    <div className="bg-background text-text-light min-h-screen font-sans">
      <header className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-8">
            <Logo />
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
