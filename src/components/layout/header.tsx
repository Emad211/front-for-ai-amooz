// components/layout/admin-header.tsx
'use client';

import { Bell, Search, Moon, Sun } from 'lucide-react';
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
} from '@/components/ui/dropdown-menu';

export function AdminHeader() {
  return (
    <header className="h-16 border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-10">
      <div className="flex items-center justify-between h-full px-6 md:px-8">
        {/* جستجو */}
        <div className="relative w-full max-w-md">
          <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input 
            placeholder="جستجو در کلاس‌ها..." 
            className="pr-10 h-10 bg-background border-border/50 rounded-xl"
          />
        </div>

        {/* اکشن‌ها */}
        <div className="flex items-center gap-2">
          {/* تم */}
          <Button variant="ghost" size="icon" className="rounded-xl">
            <Sun className="h-5 w-5 text-muted-foreground" />
          </Button>

          {/* نوتیفیکیشن */}
          <Button variant="ghost" size="icon" className="rounded-xl relative">
            <Bell className="h-5 w-5 text-muted-foreground" />
            <span className="absolute top-2 left-2 w-2 h-2 bg-primary rounded-full" />
          </Button>

          {/* پروفایل */}
          <DropdownMenu dir="rtl">
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="gap-3 px-2 rounded-xl">
                <Avatar className="h-8 w-8">
                  <AvatarImage src="https://picsum.photos/seed/admin/100/100" />
                  <AvatarFallback>AD</AvatarFallback>
                </Avatar>
                <div className="hidden md:block text-right">
                  <p className="text-sm font-medium">علی محمدی</p>
                  <p className="text-xs text-muted-foreground">مدرس</p>
                </div>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuLabel>حساب کاربری</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem>پروفایل</DropdownMenuItem>
              <DropdownMenuItem>تنظیمات</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="text-destructive">خروج</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}