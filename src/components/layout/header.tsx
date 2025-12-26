// components/layout/header.tsx
'use client';

import { Bell, Moon, Sun, Contact, LogOut, User, GraduationCap, ChevronDown } from 'lucide-react';
import Link from 'next/link';
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

const UserProfile = () => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="relative h-10 w-10 rounded-full">
          <Avatar className="h-10 w-10">
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
);


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

export function AdminHeader() {
  return (
    <header dir="rtl" className="h-20 flex items-center justify-between px-6 md:px-10 bg-card border-b border-border sticky top-0 z-50">
        {/* Logo */}
        <div className="flex items-center gap-3">
             <Link href="/home" className="flex items-center gap-2">
                <GraduationCap className="h-7 w-7 text-primary" />
                <span className="text-xl font-bold text-text-light">AI-Amooz</span>
            </Link>
        </div>

        {/* Navigation */}
        <nav className="hidden md:flex items-center bg-background/50 border border-border/50 p-1 rounded-xl">
            <NavLink href="/home">خانه</NavLink>
            <NavLink href="/classes">کلاس‌ها</NavLink>
            <NavLink href="/exam-prep">آمادگی آزمون</NavLink>
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
