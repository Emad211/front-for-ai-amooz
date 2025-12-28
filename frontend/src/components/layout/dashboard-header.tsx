// components/layout/header.tsx
'use client';

import { Bell } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { DASHBOARD_NAV_LINKS } from '@/constants/navigation';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { Logo } from '@/components/ui/logo';
import { UserProfile } from '@/components/layout/user-profile';
import { NotificationPopover } from '@/components/dashboard/notification-popover';

interface NavLinkProps {
  href: string;
  children: React.ReactNode;
}

const NavLink = ({ href, children }: NavLinkProps) => {
    const pathname = usePathname();
    const isActive = pathname.startsWith(href);
    return (
         <Link href={href} className={cn("text-sm font-medium transition-colors px-4 py-2 rounded-lg", 
            isActive ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground"
        )}>
            {children}
        </Link>
    );
};

export function DashboardHeader() {
  return (
    <header dir="rtl" className="h-16 md:h-20 flex items-center justify-between px-4 md:px-10 bg-card/80 backdrop-blur-md border-b border-border sticky top-0 z-50">
        {/* Logo */}
        <Logo imageSize="md" href="/home" className="md:hidden" showText={false} />
        <Logo imageSize="lg" href="/home" className="hidden md:flex" />

        {/* Navigation - Desktop Only */}
        <nav className="hidden md:flex items-center bg-background/50 border border-border/50 p-1 rounded-full">
            {DASHBOARD_NAV_LINKS.map((link) => (
                <NavLink key={link.href} href={link.href}>{link.label}</NavLink>
            ))}
        </nav>
        
        {/* Actions */}
        <div className="flex items-center gap-1 md:gap-2">
            <NotificationPopover />
            <div className="w-px h-6 md:h-8 bg-border mx-1 md:mx-2"></div>
            <UserProfile />
        </div>
    </header>
  );
}
