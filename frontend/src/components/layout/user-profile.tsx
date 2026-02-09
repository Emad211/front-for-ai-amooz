'use client';

import Link from 'next/link';
import { Contact, LogOut, User, Moon, Sun, Bell, Ticket } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useTheme } from 'next-themes';
import { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { getStoredUser, getStoredTokens, logout as logoutApi, clearAuthStorage } from '@/services/auth-service';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuGroup,
} from '@/components/ui/dropdown-menu';

interface UserProfileProps {
  user?: {
    name: string;
    email: string;
    avatar?: string;
  };
  isAdmin?: boolean;
}

export function UserProfile({ 
  user,
  isAdmin = false
}: UserProfileProps) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [stored, setStored] = useState<ReturnType<typeof getStoredUser> | null>(null);
  const pathname = usePathname();
  const isTeacher = pathname.startsWith('/teacher');
  const isStudent = pathname.startsWith('/home') || pathname.startsWith('/classes') || pathname.startsWith('/exam') || pathname.startsWith('/tickets') || pathname.startsWith('/profile');
  const isDashboard = isStudent || isTeacher;

  useEffect(() => {
    setMounted(true);
    setStored(getStoredUser());

    // Listen for updates
    const handleUpdate = () => {
      setStored(getStoredUser());
    };

    window.addEventListener('user-profile-updated', handleUpdate);
    return () => window.removeEventListener('user-profile-updated', handleUpdate);
  }, []);

  const displayName = (() => {
    if (user?.name) return user.name;
    const first = String(stored?.first_name ?? '').trim();
    const last = String(stored?.last_name ?? '').trim();
    const combined = `${first} ${last}`.trim();
    return combined || String(stored?.username ?? '').trim() || 'کاربر';
  })();

  const displayEmail = (() => {
    if (user?.email) return user.email;
    return String(stored?.email ?? '').trim() || '';
  })();

  const displayAvatar = (() => {
    let url = user?.avatar ?? stored?.avatar ?? undefined;
    if (url && !url.startsWith('http') && !url.startsWith('data:')) {
      const RAW_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '');
      const BASE_URL = RAW_API_URL.replace(/\/api$/, '');
      return `${BASE_URL}${url.startsWith('/') ? '' : '/'}${url}`;
    }
    return url;
  })();

  const profileHref = isTeacher ? '/teacher/settings' : '/profile';
  const ticketsHref = isTeacher ? '/teacher/tickets' : '/tickets';
  const notificationsHref = isTeacher ? '/teacher/notifications' : '/notifications';

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="relative h-10 w-10 rounded-full ring-offset-background transition-all hover:ring-2 hover:ring-primary/20">
          <Avatar className="h-10 w-10 border border-border/50">
            <AvatarImage
              src={displayAvatar}
              alt={displayName}
            />
            <AvatarFallback className="bg-primary/10 text-primary font-bold">{displayName.substring(0, 2)}</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-64 p-2 rounded-2xl shadow-2xl border-border/50" align="start" forceMount>
        <DropdownMenuLabel className="font-normal p-3">
          <div className="flex flex-col space-y-1 text-start">
            <p className="text-sm font-black leading-none text-foreground">{displayName}</p>
            <p className="text-xs leading-none text-muted-foreground font-medium">
              {displayEmail}
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator className="bg-border/50" />
        <DropdownMenuGroup className="space-y-1">
          {!isAdmin && (
            <DropdownMenuItem asChild className="justify-start rounded-xl h-11 cursor-pointer focus:bg-primary/5">
              <Link href={profileHref} className="flex items-center w-full">
                <div className="p-1.5 bg-muted/50 rounded-lg ml-2">
                  <User className="h-4 w-4 text-muted-foreground" />
                </div>
                <span className="flex-1 text-start font-bold text-sm">
                  {isTeacher ? 'تنظیمات حساب' : 'پروفایل کاربری'}
                </span>
              </Link>
            </DropdownMenuItem>
          )}
          
          {mounted && (
            <DropdownMenuItem 
              className="justify-start rounded-xl h-11 cursor-pointer focus:bg-primary/5"
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            >
              <div className="p-1.5 bg-muted/50 rounded-lg ml-2">
                {theme === 'dark' ? (
                  <Sun className="h-4 w-4 text-orange-500" />
                ) : (
                  <Moon className="h-4 w-4 text-blue-500" />
                )}
              </div>
              <span className="flex-1 text-start font-bold text-sm">
                {theme === 'dark' ? 'حالت روز' : 'حالت شب'}
              </span>
            </DropdownMenuItem>
          )}

          {!isAdmin && (
            <DropdownMenuItem asChild className="justify-start rounded-xl h-11 cursor-pointer focus:bg-primary/5">
              <Link href={notificationsHref} className="flex items-center w-full">
                <div className="p-1.5 bg-muted/50 rounded-lg ml-2">
                  <Bell className="h-4 w-4 text-muted-foreground" />
                </div>
                <span className="flex-1 text-start font-bold text-sm">اعلان‌ها</span>
              </Link>
            </DropdownMenuItem>
          )}

          {!isAdmin && (
            <DropdownMenuItem asChild className="justify-start rounded-xl h-11 cursor-pointer focus:bg-primary/5">
              <Link href={ticketsHref} className="flex items-center w-full">
                <div className="p-1.5 bg-muted/50 rounded-lg ml-2">
                  <Ticket className="h-4 w-4 text-muted-foreground" />
                </div>
                <span className="flex-1 text-start font-bold text-sm">پشتیبانی و تیکت</span>
              </Link>
            </DropdownMenuItem>
          )}
        </DropdownMenuGroup>
        <DropdownMenuSeparator className="bg-border/50" />
        <DropdownMenuItem className="justify-start rounded-xl h-11 cursor-pointer focus:bg-destructive/5 text-destructive"
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
            <div className="p-1.5 bg-destructive/10 rounded-lg ml-2">
              <LogOut className="h-4 w-4" />
            </div>
            <span className="flex-1 text-start font-bold text-sm">خروج از حساب</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
