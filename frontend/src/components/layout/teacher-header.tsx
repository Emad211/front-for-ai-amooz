'use client';

import { useEffect, useMemo, useState } from 'react';
import { usePathname } from 'next/navigation';
import { Menu } from 'lucide-react';
import { UserProfile } from '@/components/layout/user-profile';
import { Logo } from '@/components/ui/logo';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { SidebarContent } from './sidebar-content';
import { TEACHER_NAV_MENU, ORG_TEACHER_NAV_MENU } from '@/constants/navigation';
import { NotificationPopover } from '@/components/dashboard/notification-popover';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { fetchMe, getStoredTokens, getStoredUser, persistUser } from '@/services/auth-service';
import { useWorkspace } from '@/hooks/use-workspace';

export function TeacherHeader() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const { isOrgMode, activeWorkspace } = useWorkspace();
  const currentNavMenu = isOrgMode ? ORG_TEACHER_NAV_MENU : TEACHER_NAV_MENU;
  const currentPanelLabel = isOrgMode ? (activeWorkspace?.name ?? 'سازمان') : 'پنل معلم';

  // Avoid SSR/CSR hydration mismatch by not reading localStorage during the initial render.
  const [me, setMe] = useState<ReturnType<typeof getStoredUser>>(null);
  const [hasMounted, setHasMounted] = useState(false);

  useEffect(() => {
    setHasMounted(true);

    const stored = getStoredUser();
    if (stored) setMe(stored);

    const tokens = getStoredTokens();
    if (!tokens?.access) return;

    // Best-effort refresh from backend; keep UI responsive with stored user.
    fetchMe(tokens.access)
      .then((fresh) => {
        persistUser(fresh);
        setMe(fresh);
      })
      .catch(() => {
        // Ignore; header can still render from local storage.
      });
  }, []);

  const displayName = useMemo(() => {
    const anyMe = me as any;
    const first = (anyMe?.first_name as string | undefined)?.trim() || '';
    const last = (anyMe?.last_name as string | undefined)?.trim() || '';
    const full = `${first} ${last}`.trim();
    return (
      full ||
      first ||
      (anyMe?.username as string | undefined)?.trim() ||
      'کاربر'
    );
  }, [me]);

  const displayEmail = useMemo(() => {
    const anyMe = me as any;
    return (anyMe?.email as string | undefined) || '';
  }, [me]);

  const displayAvatar = useMemo(() => {
    const anyMe = me as any;
    return (anyMe?.avatar as string | undefined) || '';
  }, [me]);

  const lastSegment = pathname.split('/').filter(Boolean).pop() || 'teacher';
  const personalTitleMap: Record<string, string> = {
    teacher: 'داشبورد معلم',
    analytics: 'آمار و تحلیل',
    'create-class': 'ایجاد کلاس جدید',
    'my-classes': 'کلاس‌های من',
    'my-exams': 'آزمون‌های من',
    students: 'مدیریت دانش‌آموزان',
    messages: 'پیام‌رسانی',
    settings: 'تنظیمات پنل',
  };
  const orgTitleMap: Record<string, string> = {
    teacher: 'داشبورد سازمان',
    analytics: 'آمار و تحلیل',
    'create-class': 'ایجاد کلاس جدید',
    'my-classes': 'کلاس‌های سازمان',
    'my-exams': 'آزمون‌های سازمان',
    students: 'مدیریت دانش‌آموزان',
    messages: 'پیام‌رسانی',
    settings: 'تنظیمات پنل',
  };
  const titleMap = isOrgMode ? orgTitleMap : personalTitleMap;
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
                navMenu={currentNavMenu}
                panelLabel={currentPanelLabel}
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
            خوش آمدید، {hasMounted ? displayName : 'کاربر'} عزیز
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 md:gap-3">
        <div className="flex items-center gap-1 md:gap-2 bg-background/50 p-1 rounded-2xl border border-border/50">
          <ThemeToggle className="h-9 w-9 rounded-xl hover:bg-primary/10 hover:text-primary transition-colors" />
          <NotificationPopover />
          <div className="w-px h-6 bg-border/50 mx-1"></div>
          <UserProfile isAdmin={false} />
        </div>
      </div>
    </header>
  );
}
