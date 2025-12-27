// components/layout/admin-sidebar.tsx
'use client';

import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { 
  Settings,
  LogOut,
  ChevronLeft
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { ADMIN_NAV_MENU } from '@/constants/navigation';
import { Logo } from '@/components/ui/logo';

export function AdminSidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 min-h-screen bg-card border-l border-border flex flex-col">
      {/* لوگو */}
      <div className="p-6">
        <Logo 
          href="/admin" 
          imageSize="lg" 
          textClassName="text-lg"
        />
        <p className="text-xs text-muted-foreground mr-14 -mt-1">پنل مدیریت</p>
      </div>

      <Separator className="bg-border/50" />

      {/* منوها */}
      <nav className="flex-1 p-4 space-y-6">
        {ADMIN_NAV_MENU.map((section, idx) => (
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
          onClick={() => {
            // Clear any stored auth tokens
            if (typeof window !== 'undefined') {
              localStorage.removeItem('authToken');
              sessionStorage.removeItem('authToken');
            }
            // Redirect to landing page
            window.location.href = '/';
          }}
        >
          <LogOut className="h-5 w-5" />
          <span>خروج از حساب</span>
        </Button>
      </div>
    </aside>
  );
}
