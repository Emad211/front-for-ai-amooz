// components/layout/header.tsx
'use client';

import type { ReactNode } from 'react';
import { Bell, Moon, Sun, Contact, LogOut, User, GraduationCap, ChevronDown, Ticket } from 'lucide-react';
import Link from 'next/link';
import Image from 'next/image';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuGroup,
} from '@/components/ui/dropdown-menu';
import { useTheme } from 'next-themes';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { getStoredUser, getStoredTokens, logout as logoutApi, clearAuthStorage, type AuthMeResponse } from '@/services/auth-service';
import { useEffect, useState } from 'react';

type NavLinkProps = {
  href: string;
  children: ReactNode;
};

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

const UserProfile = () => {
    const [user, setUser] = useState<AuthMeResponse | null>(null);

    useEffect(() => {
        // Initial load
        setUser(getStoredUser());

        // Listen for updates
        const handleUpdate = () => {
            setUser(getStoredUser());
        };

        window.addEventListener('user-profile-updated', handleUpdate);
        return () => window.removeEventListener('user-profile-updated', handleUpdate);
    }, []);
    
    // Construct avatar URL if needed
    let avatarUrl = user?.avatar;
    if (avatarUrl && !avatarUrl.startsWith('http') && !avatarUrl.startsWith('data:')) {
      const RAW_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');
      const BASE_URL = RAW_API_URL.replace(/\/api$/, '');
      avatarUrl = `${BASE_URL}${avatarUrl.startsWith('/') ? '' : '/'}${avatarUrl}`;
    }

    const initials = user?.first_name || user?.last_name 
      ? `${(user.first_name?.[0] || '')}${(user.last_name?.[0] || '')}`.toUpperCase()
      : (user?.username?.[0] || 'U').toUpperCase();

    const fullName = user?.first_name || user?.last_name 
      ? `${user.first_name || ''} ${user.last_name || ''}`.trim() 
      : user?.username;

    return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="relative h-10 w-10 rounded-full">
          <Avatar className="h-10 w-10 overflow-hidden ring-2 ring-background ring-offset-2 ring-offset-primary/20">
            <AvatarImage
              src={avatarUrl || undefined}
              alt={fullName || 'پروفایل'}
              className="object-cover"
            />
            <AvatarFallback className="bg-primary/10 text-primary font-bold">
                {initials}
            </AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56" align="end" forceMount>
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col space-y-2 py-1">
            <p className="text-sm font-semibold leading-none">{fullName}</p>
            <p className="text-xs leading-none text-muted-foreground truncate">
              {user?.email}
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem asChild className="cursor-pointer">
            <Link href="/profile" className="flex items-center w-full">
              <User className="ml-2 h-4 w-4 text-muted-foreground" />
              <span>پروفایل</span>
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild className="cursor-pointer">
            <Link href="/notifications" className="flex items-center w-full">
              <Bell className="ml-2 h-4 w-4 text-muted-foreground" />
              <span>اعلان‌ها</span>
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild className="cursor-pointer">
            <Link href="/tickets" className="flex items-center w-full">
              <Ticket className="ml-2 h-4 w-4 text-muted-foreground" />
              <span>پشتیبانی و تیکت</span>
            </Link>
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="cursor-pointer text-destructive focus:text-destructive"
          onClick={async () => {
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
            <LogOut className="ml-2 h-4 w-4" />
            <span>خروج</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
    );
};


const ThemeToggle = () => {
    const { theme, setTheme } = useTheme();
    return (
        <Button variant="ghost" size="icon" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
            <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
            <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
            <span className="sr-only">Toggle theme</span>
        </Button>
    )
}

export function DashboardHeader() {
  return (
    <header dir="rtl" className="h-20 flex items-center justify-between px-6 md:px-10 bg-card border-b border-border sticky top-0 z-50">
        {/* Logo */}
        <div className="flex items-center gap-3">
             <Link href="/home" className="flex items-center gap-2 group relative">
                <div className="relative h-12 w-16">
                    <Image
                        src="/logo (2).png"
                        alt="AI-Amooz logo"
                        fill
                        sizes="128px"
                        className="object-contain transition-all duration-300 scale-[2.2] origin-center"
                        priority
                    />
                </div>
                <span className="text-xl font-bold text-text-light ml-2">AI-Amooz</span>
            </Link>
        </div>

        {/* Navigation */}
        <nav className="hidden md:flex items-center bg-background/50 border border-border/50 p-1 rounded-full">
            <NavLink href="/home">خانه</NavLink>
            <NavLink href="/classes">کلاس‌ها</NavLink>
            <NavLink href="/exam-prep">آمادگی آزمون</NavLink>
        </nav>
        
        {/* Actions */}
        <div className="flex items-center gap-2">
            <ThemeToggle />
            <div className="w-px h-8 bg-border mx-2"></div>
            <UserProfile />
        </div>
    </header>
  );
}
