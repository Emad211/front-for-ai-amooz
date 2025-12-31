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

export function TeacherHeader() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);

  const lastSegment = pathname.split('/').filter(Boolean).pop() || 'teacher';
  const titleMap: Record<string, string> = {
    teacher: 'داشبورد معلم',
    analytics: 'آمار',
    'create-class': 'ایجاد کلاس',
    'my-classes': 'کلاس‌های من',
    students: 'دانش‌آموزان',
    messages: 'پیام‌ها',
    settings: 'تنظیمات',
  };
  const pageTitle = titleMap[lastSegment] ?? titleMap.teacher;

  return (
    <header className="flex items-center justify-between gap-4">
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
        
        <div className="flex items-center gap-2 text-lg md:text-xl font-black text-foreground">
          <span className="text-foreground">{pageTitle}</span>
        </div>
      </div>

      <div className="flex items-center gap-2 md:gap-3">
        <div className="flex items-center gap-1 md:gap-2">
          <UserProfile user={{
            name: 'معلم',
            email: 'teacher@example.com',
            avatar: ''
          }} isAdmin={false} />
        </div>
      </div>
    </header>
  );
}
