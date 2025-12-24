
"use client";

import { Bell, BookOpen, Calendar, ChevronRight, ChevronLeft, GraduationCap, History, LogOut, Medal, Target, Clock, Video, FileText } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

const StatCard = ({ title, value, subValue, icon, tag }) => (
  <Card className="bg-card flex-1 min-w-[220px]">
    <CardHeader className="flex flex-row items-center justify-between pb-2 text-text-secondary">
      <h3 className="text-sm font-medium">{title}</h3>
      {tag && <div className="text-xs font-semibold px-2 py-1 rounded-full bg-btn-primary/20 text-accent-mint">{tag}</div>}
    </CardHeader>
    <CardContent className="flex items-center gap-4">
      <div className="bg-btn-primary/10 p-3 rounded-md">
        {icon}
      </div>
      <div className="flex flex-col">
        <p className="text-2xl font-bold text-text-on-dark">{value}</p>
        <p className="text-xs text-text-secondary">{subValue}</p>
      </div>
    </CardContent>
  </Card>
);

const EventCard = ({ title, status, type, icon, date, month }) => (
  <div className="flex items-center justify-between bg-card p-4 rounded-lg">
    <div className="flex items-center gap-4">
      <div className="flex flex-col items-center justify-center bg-btn-primary/20 text-accent-mint rounded-lg w-12 h-12">
        <span className="text-sm font-bold">{date}</span>
        <span className="text-xs">{month}</span>
      </div>
      <div>
        <h4 className="font-semibold text-text-on-dark">{title}</h4>
        <p className="text-xs text-text-secondary flex items-center gap-2">
            {icon}
            <span>{status}</span>
        </p>
      </div>
    </div>
    <Button variant="ghost" size="icon">
        <ChevronRight className="h-5 w-5 text-text-secondary"/>
    </Button>
  </div>
);

const ActivityCard = ({ title, time, type, icon }) => (
  <div className="flex items-center justify-between bg-card p-4 rounded-lg">
    <div className="flex items-center gap-4">
       <div className="p-2 bg-btn-primary/20 text-accent-mint rounded-md">{icon}</div>
      <div>
        <h4 className="font-semibold text-text-on-dark">{title}</h4>
        <div className="flex items-center gap-4 text-xs text-text-secondary">
          <span>{time}</span>
          <span className="text-accent-mint bg-accent-mint/10 px-2 py-0.5 rounded-full">{type}</span>
        </div>
      </div>
    </div>
     <Button variant="ghost" size="icon">
        <ChevronRight className="h-5 w-5 text-text-secondary"/>
    </Button>
  </div>
);


export default function StudentDashboard() {
  return (
    <div className="bg-background text-text-on-dark min-h-screen font-sans">
      <header className="flex items-center justify-between p-4 border-b border-btn-hover">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2">
            <GraduationCap className="h-8 w-8 text-accent-mint" />
            <h1 className="text-xl font-bold">AI-Amooz</h1>
          </div>
          <nav className="hidden md:flex items-center gap-1 bg-card p-1 rounded-full">
            <Button variant="ghost" className="bg-btn-primary text-text-on-dark rounded-full">داشبورد</Button>
            <Button variant="ghost" className="text-text-secondary rounded-full">کلاس‌ها</Button>
            <Button variant="ghost" className="text-text-secondary rounded-full">آمادگی آزمون</Button>
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" className="relative">
            <Bell className="h-5 w-5 text-text-secondary" />
             <span className="absolute top-1 right-1 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-mint opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-mint"></span>
            </span>
          </Button>
          <div className="flex items-center gap-3">
             <div className="text-left hidden sm:block">
              <p className="font-semibold text-sm">علی رضایی</p>
              <p className="text-xs text-text-secondary">دانش آموز ممتاز</p>
            </div>
            <Avatar>
              <AvatarImage src="https://picsum.photos/seed/user/40/40" alt="Ali Rezaei" />
              <AvatarFallback>AR</AvatarFallback>
            </Avatar>
          </div>
           <Button variant="ghost" size="icon">
             <LogOut className="h-5 w-5 text-text-secondary" />
           </Button>
        </div>
      </header>

      <main className="p-4 md:p-8 space-y-8">
        <div className="bg-gradient-to-r from-btn-primary to-btn-hover p-8 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="text-right">
            <div className="inline-flex items-center gap-2 bg-accent-mint/20 text-accent-mint text-xs font-semibold px-3 py-1 rounded-full mb-4">
                <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-mint opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-mint"></span>
                </span>
              هوش مصنوعی فعال است
            </div>
            <h2 className="text-3xl font-bold mb-2">👋 خوش آمدید به AI-Amooz</h2>
            <p className="text-text-on-dark/80 max-w-lg">
              مسیر یادگیری شما با هوش مصنوعی بهینه سازی شده است. آماده ادامه فیزیک کوانتوم هستید؟
            </p>
          </div>
          <Button size="lg" className="bg-accent-mint text-bg-hero-dark hover:bg-accent-mint/90 flex-shrink-0">
            <ChevronRight className="ml-2 h-5 w-5" />
            ادامه یادگیری هوشمند
          </Button>
        </div>
        
        <div className="flex flex-wrap gap-6">
          <StatCard title="پیشرفت دوره‌ها" value="۵/۸" subValue="دوره فعال" icon={<BookOpen className="text-accent-mint"/>} />
          <StatCard title="درصد تکمیل" value="۷۵٪" subValue="میانگین کل" icon={<Target className="text-accent-mint"/>} tag="ترم جاری"/>
          <StatCard title="زمان مطالعه" value="۱۲:۳۰" subValue="ساعت مفید" icon={<Clock className="text-accent-mint"/>} tag="این هفته"/>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <section>
                 <div className="flex items-center justify-between mb-4">
                    <h3 className="flex items-center gap-2 text-xl font-bold"><History className="text-accent-mint"/> فعالیت‌های اخیر</h3>
                    <Button variant="link" className="text-accent-mint"><ChevronLeft className="h-4 w-4 ml-1"/> مشاهده همه</Button>
                </div>
                <div className="space-y-4">
                   <ActivityCard title="ریاضیات گسسته - فصل ۲" time="۲ ساعت پیش" type="در حال انجام" icon={<FileText className="text-current"/>} />
                   <ActivityCard title="فیزیک کوانتوم - مقدمه" time="دیروز" type="ویدیو" icon={<Video className="text-current"/>} />
                   <ActivityCard title="زبان انگلیسی تخصصی" time="۳ روز پیش" type="آزمون" icon={<Medal className="text-current"/>} />
                </div>
            </section>
            
             <section>
                <div className="flex items-center justify-between mb-4">
                    <h3 className="flex items-center gap-2 text-xl font-bold"><Calendar className="text-accent-mint"/> رویدادهای پیش رو</h3>
                    <Button variant="link" className="text-accent-mint">مشاهده تقویم کامل</Button>
                </div>
                <div className="space-y-4">
                    <EventCard title="آزمون میان‌ترم ریاضی" status="ساعت ۱۰:۰۰ - آنلاین" date="۱۵" month="تیر" icon={<Clock className="h-3 w-3 text-current"/>}/>
                    <EventCard title="تحویل پروژه فیزیک" status="تا پایان روز" date="۲۰" month="تیر" icon={<Calendar className="h-3 w-3 text-current"/>}/>
                </div>
            </section>
        </div>

      </main>
    </div>
  );
}
