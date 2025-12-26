// components/layout/admin-header.tsx
'use client';

import { Bell, Search, Moon, Sun, Settings, Contact, LogOut, User } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
import { ThemeToggle } from '../theme-toggle';


const Actions = () => (
  <div className="flex items-center gap-4">
      <ThemeToggle />
      <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          <span className="absolute top-2.5 right-2.5 w-2 h-2 bg-primary rounded-full border-2 border-background"></span>
      </Button>
  </div>
);


const UserProfile = () => (
  <div className="flex items-center gap-4">
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="relative h-10 w-10 rounded-full">
          <Avatar className="h-9 w-9">
            <AvatarImage
              src="https://picsum.photos/seed/user/100/100"
              alt="Alireza"
            />
            <AvatarFallback>AR</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56" align="end" forceMount>
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col space-y-1">
            <p className="text-sm font-medium leading-none">علیرضا رضایی</p>
            <p className="text-xs leading-none text-muted-foreground">
              ali.rezaei@example.com
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem asChild>
            <Link href="/profile">
              <User className="ml-2 h-4 w-4" />
              <span>پروفایل</span>
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem>
            <Contact className="ml-2 h-4 w-4" />
            <span>پشتیبانی</span>
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/login">
            <LogOut className="ml-2 h-4 w-4" />
            <span>خروج</span>
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  </div>
);


export function AdminHeader() {
  const { theme, setTheme } = useTheme();

  return (
    <header dir="rtl" className="h-20 flex items-center justify-between px-6 md:px-10 bg-card border-b border-border sticky top-0 z-50">
        <div className="flex-1 max-w-md relative">
           <Input
                type="search"
                placeholder="جستجوی دوره، استاد یا مبحث..."
                className="bg-background border-border h-11 pl-4 pr-10 rounded-lg focus:ring-primary focus:border-primary w-full"
            />
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
        </div>
        <div className="flex items-center gap-4">
            <Actions />
            <div className="w-px h-8 bg-border mx-2"></div>
            <UserProfile />
        </div>
    </header>
  );
}
