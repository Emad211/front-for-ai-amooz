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

const NavLink = ({ href, children }) => {
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
    <header dir="rtl" className="h-20 flex items-center justify-between px-6 md:px-10 bg-card border-b border-border sticky top-0 z-50">
        {/* Logo */}
        <Logo imageSize="lg" href="/home" />

        {/* Navigation */}
        <nav className="hidden md:flex items-center bg-background/50 border border-border/50 p-1 rounded-full">
            {DASHBOARD_NAV_LINKS.map((link) => (
                <NavLink key={link.href} href={link.href}>{link.label}</NavLink>
            ))}
        </nav>
        
        {/* Actions */}
        <div className="flex items-center gap-2">
            <ThemeToggle />
            <Button variant="ghost" size="icon" className="relative">
                <Bell className="h-5 w-5" />
                <span className="absolute top-2.5 right-2.5 w-2 h-2 bg-primary rounded-full border-2 border-background"></span>
            </Button>
            <div className="w-px h-8 bg-border mx-2"></div>
            <UserProfile />
        </div>
    </header>
  );
}
