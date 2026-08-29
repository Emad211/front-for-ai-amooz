'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { NotebookPen } from 'lucide-react';
import { cn } from '@/lib/utils';
import { DASHBOARD_NAV_LINKS } from '@/constants/navigation';
import type { NavItem } from '@/types';
import { useActiveAdvisor } from '@/hooks/use-active-advisor';

// Render-site injection only: DASHBOARD_NAV_LINKS itself must stay untouched
// so the entry stays hidden for every student without an active advisor.
const STUDY_LOG_NAV_ITEM: NavItem = {
  label: 'گزارش روزانه',
  href: '/study-log',
  icon: NotebookPen,
};

export function MobileNav() {
  const pathname = usePathname();
  // null (loading) → base links only; the entry must never flash.
  const { hasActiveAdvisor } = useActiveAdvisor();
  const links = hasActiveAdvisor
    ? [...DASHBOARD_NAV_LINKS, STUDY_LOG_NAV_ITEM]
    : DASHBOARD_NAV_LINKS;

  return (
    <div className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-lg border-t border-border px-3 py-2">
      <nav className="flex items-center justify-around w-full">
        {links.map((link) => {
          // Match subroutes too (e.g. /exercises/12) — same behavior as the desktop nav.
          const isActive = pathname === link.href || pathname.startsWith(`${link.href}/`);
          const Icon = link.icon;
          
          return (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "flex flex-col items-center gap-1 transition-all duration-300 relative",
                isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <div className={cn(
                "p-2 rounded-xl transition-all duration-300",
                isActive ? "bg-primary/10 scale-110" : "bg-transparent"
              )}>
                <Icon className={cn("h-6 w-6", isActive ? "stroke-[2.5px]" : "stroke-[2px]")} />
              </div>
              <span className={cn(
                "text-[10px] font-bold transition-all duration-300",
                isActive ? "opacity-100 translate-y-0" : "opacity-70"
              )}>
                {link.label}
              </span>
              {isActive && (
                <span className="absolute -top-1 w-1 h-1 bg-primary rounded-full animate-pulse"></span>
              )}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
