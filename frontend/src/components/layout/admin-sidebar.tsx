// components/layout/admin-sidebar.tsx
'use client';

import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { 
  GraduationCap, 
  PlusCircle, 
  FolderOpen, 
  Users, 
  BarChart3, 
  Settings,
  LogOut,
  ChevronLeft
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';

const menuItems = [
  {
    title: 'مدیریت کلاس‌ها',
    items: [
      { label: 'ایجاد کلاس جدید', href: '/admin/create-class', icon: PlusCircle },
      { label: 'کلاس‌های من', href: '/admin/my-classes', icon: FolderOpen },
      { label: 'دانش‌آموزان', href: '/admin/students', icon: Users },
    ]
  },
  {
    title: 'گزارشات',
    items: [
      { label: 'آمار و تحلیل', href: '/admin/analytics', icon: BarChart3 },
    ]
  },
];

export function AdminSidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 min-h-screen bg-card border-l border-border flex flex-col">
      {/* لوگو */}
      <div className="p-6">
        <Link href="/admin" className="flex items-center gap-3 group relative">
          <div className="relative h-12 w-16">
            <Image
              src="/logo (2).png"
              alt="AI-Amooz logo"
              fill
              sizes="128px"
              className="object-contain mix-blend-screen brightness-125 scale-[2.2] origin-center"
              priority
            />
          </div>
          <div>
            <span className="text-lg font-bold text-foreground ml-2">AI-Amooz</span>
            <p className="text-xs text-muted-foreground">پنل مدیریت</p>
          </div>
        </Link>
      </div>

      <Separator className="bg-border/50" />

      {/* منوها */}
      <nav className="flex-1 p-4 space-y-6">
        {menuItems.map((section, idx) => (
          <div key={idx}>
            <h3 className="text-xs font-medium text-muted-foreground mb-3 px-3">
              {section.title}
            </h3>
            <ul className="space-y-1">
              {section.items.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200",
                        isActive 
                          ? "bg-primary text-primary-foreground shadow-md" 
                          : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                      )}
                    >
                      <item.icon className="h-5 w-5" />
                      <span className="flex-1">{item.label}</span>
                      {isActive && <ChevronLeft className="h-4 w-4" />}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <Separator className="bg-border/50" />

      {/* پایین سایدبار */}
      <div className="p-4 space-y-1">
        <Link
          href="/admin/settings"
          className={cn(
            "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200",
            pathname === '/admin/settings'
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
          )}
        >
          <Settings className="h-5 w-5" />
          <span>تنظیمات</span>
        </Link>
        
        <Button 
          variant="ghost" 
          className="w-full justify-start gap-3 px-3 py-2.5 h-auto text-sm font-medium text-muted-foreground hover:text-destructive hover:bg-destructive/10"
        >
          <LogOut className="h-5 w-5" />
          <span>خروج از حساب</span>
        </Button>
      </div>
    </aside>
  );
}
