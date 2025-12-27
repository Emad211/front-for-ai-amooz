'use client';

import { Button } from '@/components/ui/button';
import { ChevronLeft, Grid, History, Settings, Bell } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { UserProfile } from '@/components/layout/user-profile';

import { Logo } from '@/components/ui/logo';

export function AdminHeader() {
  const pathname = usePathname();
  // A simple way to get a readable title from the path
  const pageTitle = pathname.split('/').pop()?.replace(/-/g, ' ') || 'Dashboard';

  return (
    <header className="flex items-center justify-between gap-4">
      <div className="flex items-center gap-4">
        {/* Mobile Logo */}
        <div className="lg:hidden">
          <Logo href="/admin" imageSize="sm" showText={false} />
        </div>
        <div className="flex items-center gap-2 text-xl font-black text-foreground">
          <span className="capitalize text-base md:text-xl text-foreground">{pageTitle}</span>
        </div>
      </div>

      <div className="flex items-center gap-2 md:gap-3">
        <div className="hidden sm:flex items-center gap-1 bg-muted/50 p-1 rounded-xl border border-border/50">
          <Button variant="ghost" size="icon" className="h-8 w-8 md:h-9 md:w-9 rounded-lg">
            <Grid className="h-4 w-4 text-muted-foreground" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8 md:h-9 md:w-9 rounded-lg">
            <History className="h-4 w-4 text-muted-foreground" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8 md:h-9 md:w-9 rounded-lg">
            <Settings className="h-4 w-4 text-muted-foreground" />
          </Button>
        </div>
        
        <div className="hidden sm:block w-px h-6 bg-border mx-1"></div>
        
        <div className="flex items-center gap-1 md:gap-2">
          <Button variant="ghost" size="icon" className="relative h-9 w-9 md:h-10 md:w-10">
            <Bell className="h-4 w-4 md:h-5 md:w-5" />
            <span className="absolute top-2 right-2 md:top-2.5 md:right-2.5 w-2 h-2 bg-primary rounded-full border-2 border-background"></span>
          </Button>
          <UserProfile />
        </div>
      </div>
    </header>
  );
}
