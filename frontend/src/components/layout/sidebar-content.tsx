'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  Settings,
  LogOut,
  ChevronLeft
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { ADMIN_NAV_MENU, TEACHER_NAV_MENU } from '@/constants/navigation';
import { Logo } from '@/components/ui/logo';
import { clearAuthStorage, getStoredTokens, logout as logoutApi } from '@/services/auth-service';

interface SidebarContentProps {
  onItemClick?: () => void;
  navMenu?: typeof ADMIN_NAV_MENU | typeof TEACHER_NAV_MENU;
  panelLabel?: string;
  logoHref?: string;
  settingsHref?: string;
}

export function SidebarContent({ onItemClick, navMenu = ADMIN_NAV_MENU, panelLabel = 'پنل مدیریت', logoHref = '/admin', settingsHref }: SidebarContentProps) {
  const pathname = usePathname();
  const resolvedSettingsHref = settingsHref ?? `${logoHref}/settings`;

  return (
    <div className="flex flex-col h-full">
      {/* لوگو */}
      <div className="p-6">
        <Logo 
          href={logoHref} 
          imageSize="lg" 
          textClassName="text-lg"
        />
        <p className="text-xs text-muted-foreground ms-[72px] -mt-1 font-medium">{panelLabel}</p>
      </div>

      <Separator className="bg-border/50" />

      {/* منوها */}
      <nav className="flex-1 p-4 space-y-6 overflow-y-auto">
        {navMenu.map((section, idx) => (
          <div key={idx}>
            <h3 className="text-xs font-bold text-muted-foreground/60 mb-3 px-3 uppercase tracking-wider">
              {section.title}
            </h3>
            <ul className="space-y-1">
              {section.items.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onItemClick}
                      className={cn(
                        "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-bold transition-all duration-200",
                        isActive 
                          ? "bg-primary text-primary-foreground shadow-lg shadow-primary/20" 
                          : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                      )}
                    >
                      <item.icon className={cn("h-5 w-5", isActive ? "text-primary-foreground" : "text-muted-foreground")} />
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
          href={resolvedSettingsHref}
          onClick={onItemClick}
          className={cn(
            "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-bold transition-all duration-200",
            pathname === resolvedSettingsHref
              ? "bg-primary text-primary-foreground shadow-lg shadow-primary/20"
              : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
          )}
        >
          <Settings className="h-5 w-5" />
          <span>تنظیمات</span>
        </Link>
        
        <Button 
          variant="ghost" 
          className="w-full justify-start gap-3 px-3 py-2.5 h-auto text-sm font-bold text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-xl"
          onClick={async () => {
            if (onItemClick) onItemClick();
            try {
              const tokens = getStoredTokens();
              if (tokens?.refresh) {
                await logoutApi(tokens.refresh, tokens.access).catch(() => {});
              }
            } finally {
              clearAuthStorage();
              window.location.href = '/login';
            }
          }}
        >
          <LogOut className="h-5 w-5" />
          <span>خروج از حساب</span>
        </Button>
      </div>
    </div>
  );
}
