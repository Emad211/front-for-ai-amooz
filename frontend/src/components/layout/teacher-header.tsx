'use client';

import { useState } from 'react';
import { usePathname } from 'next/navigation';
import { Menu } from 'lucide-react';
import { UserProfile } from '@/components/layout/user-profile';
import { Logo } from '@/components/ui/logo';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { SidebarContent } from './sidebar-content';
import { TEACHER_NAV_MENU } from '@/constants/navigation';
import { NotificationPopover } from '@/components/dashboard/notification-popover';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { MOCK_TEACHER_PROFILE } from '@/constants/mock/user-data';

export function TeacherHeader() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);

  const lastSegment = pathname.split('/').filter(Boolean).pop() || 'teacher';
  const titleMap: Record<string, string> = {
    teacher: 'داشبورد معلم',
    analytics: 'آمار و تحلیل',
    'create-class': 'ایجاد کلاس جدید',
    'my-classes': 'کلاس‌های من',
    students: 'مدیریت دانش‌آموزان',
    messages: 'پیام‌رسانی',
    settings: 'تنظیمات پنل',
  };
  const pageTitle = titleMap[lastSegment] ?? titleMap.teacher;

  return (
    <header className="flex items-center justify-between gap-4 bg-card/50 backdrop-blur-md p-4 rounded-3xl border border-border/50 shadow-sm">
      <div className="flex items-center gap-2 md:gap-4">
        <div className="lg:hidden">
          <Sheet open={isOpen} onOpenChange={setIsOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="h-10 w-10 rounded-xl bg-muted/50">
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="p-0 w-72 border-l-border">
              <div className="sr-only">
                <SheetHeader>
                  <SheetTitle>منوی معلم</SheetTitle>
                  <SheetDescription>دسترسی به بخش‌های مختلف پنل معلم</SheetDescription>
                </SheetHeader>
              </div>
              <SidebarContent
                navMenu={TEACHER_NAV_MENU}
                panelLabel="پنل معلم"
                logoHref="/teacher"
                settingsHref="/teacher/settings"
                onItemClick={() => setIsOpen(false)}
              />
            </SheetContent>
          </Sheet>
        </div>

        <div className="hidden sm:block lg:hidden">
          <Logo href="/teacher" imageSize="sm" showText={false} />
        </div>
        
        <div className="flex flex-col">
          <h1 className="text-lg md:text-xl font-black text-foreground leading-none">
            {pageTitle}
          </h1>
          <p className="text-[10px] text-muted-foreground font-medium mt-1 hidden md:block">
            خوش آمدید، {MOCK_TEACHER_PROFILE.name} عزیز
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 md:gap-3">
        <div className="flex items-center gap-1 md:gap-2 bg-background/50 p-1 rounded-2xl border border-border/50">
          <ThemeToggle className="h-9 w-9 rounded-xl hover:bg-primary/10 hover:text-primary transition-colors" />
          <NotificationPopover />
          <div className="w-px h-6 bg-border/50 mx-1"></div>
          <UserProfile 
            user={{
              name: MOCK_TEACHER_PROFILE.name,
              email: MOCK_TEACHER_PROFILE.email,
              avatar: MOCK_TEACHER_PROFILE.avatar
            }} 
            isAdmin={false} 
          />
        </div>
      </div>
    </header>
  );
}
