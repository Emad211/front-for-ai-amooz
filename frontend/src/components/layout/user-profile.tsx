'use client';

import Link from 'next/link';
import { Contact, LogOut, User, Moon, Sun, Bell, Ticket } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useTheme } from 'next-themes';
import { useState, useEffect } from 'react';
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
  user = {
    name: 'علیرضا رضایی',
    email: 'ali.rezaei@example.com',
    avatar: 'https://picsum.photos/seed/user/100/100'
  },
  isAdmin = false
}: UserProfileProps) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="relative h-10 w-10 rounded-full ring-offset-background transition-all hover:ring-2 hover:ring-primary/20">
          <Avatar className="h-10 w-10 border border-border/50">
            <AvatarImage
              src={user.avatar}
              alt={user.name}
            />
            <AvatarFallback className="bg-primary/10 text-primary font-bold">{user.name.substring(0, 2)}</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-64 p-2 rounded-2xl shadow-2xl border-border/50" align="start" forceMount>
        <DropdownMenuLabel className="font-normal p-3">
          <div className="flex flex-col space-y-1 text-start">
            <p className="text-sm font-black leading-none text-foreground">{user.name}</p>
            <p className="text-xs leading-none text-muted-foreground font-medium">
              {user.email}
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator className="bg-border/50" />
        <DropdownMenuGroup className="space-y-1">
          {!isAdmin && (
            <DropdownMenuItem asChild className="justify-start rounded-xl h-11 cursor-pointer focus:bg-primary/5">
              <Link href="/profile" className="flex items-center w-full">
                <div className="p-1.5 bg-muted/50 rounded-lg ml-2">
                  <User className="h-4 w-4 text-muted-foreground" />
                </div>
                <span className="flex-1 text-start font-bold text-sm">پروفایل کاربری</span>
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
              <Link href="/tickets" className="flex items-center w-full">
                <div className="p-1.5 bg-muted/50 rounded-lg ml-2">
                  <Ticket className="h-4 w-4 text-muted-foreground" />
                </div>
                <span className="flex-1 text-start font-bold text-sm">پشتیبانی و تیکت</span>
              </Link>
            </DropdownMenuItem>
          )}
        </DropdownMenuGroup>
        <DropdownMenuSeparator className="bg-border/50" />
        <DropdownMenuItem asChild className="justify-start rounded-xl h-11 cursor-pointer focus:bg-destructive/5 text-destructive">
           <Link href="/" className="flex items-center w-full">
            <div className="p-1.5 bg-destructive/10 rounded-lg ml-2">
              <LogOut className="h-4 w-4" />
            </div>
            <span className="flex-1 text-start font-bold text-sm">خروج از حساب</span>
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
