'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { DASHBOARD_NAV_LINKS } from '@/constants/navigation';

export function MobileNav() {
  const pathname = usePathname();

  return (
    <div className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-lg border-t border-border px-6 py-3">
      <nav className="flex items-center justify-between max-w-md mx-auto">
        {DASHBOARD_NAV_LINKS.map((link) => {
          const isActive = pathname === link.href;
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
