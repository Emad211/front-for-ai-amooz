'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Bell,
  BookOpen,
  GraduationCap,
  Home,
  LogOut,
  Moon,
  Settings,
  Sun,
  User,
} from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import { ThemeToggle } from '../theme-toggle';

const Logo = () => (
  <Link href="/" className="flex items-center gap-2">
    <GraduationCap className="h-7 w-7 text-primary" />
    <span className="text-xl font-bold text-text-light">AI-Amooz</span>
  </Link>
);

const NavItem = ({ href, children }) => {
  const pathname = usePathname();
  const isActive = pathname === href;

  return (
    <Link
      href={href}
      className={cn(
        'rounded-full px-4 py-2 text-sm font-medium transition-colors',
        isActive
          ? 'bg-primary text-primary-foreground'
          : 'text-muted-foreground hover:text-foreground'
      )}
    >
      {children}
    </Link>
  );
};

const UserProfile = () => (
  <DropdownMenu>
    <DropdownMenuTrigger asChild>
      <Button variant="ghost" className="relative h-10 w-10 rounded-full">
        <Avatar className="h-9 w-9">
          <AvatarImage src="https://picsum.photos/seed/user/100/100" alt="Alireza" />
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
          <Settings className="ml-2 h-4 w-4" />
          <span>تنظیمات</span>
        </DropdownMenuItem>
      </DropdownMenuGroup>
      <DropdownMenuSeparator />
       <DropdownMenuItem>
         <ThemeToggle />
      </DropdownMenuItem>
      <DropdownMenuSeparator />
      <DropdownMenuItem>
        <LogOut className="ml-2 h-4 w-4" />
        <span>خروج</span>
      </DropdownMenuItem>
    </DropdownMenuContent>
  </DropdownMenu>
);

export function Header() {
  return (
    <header className="flex h-16 items-center justify-between px-4 md:px-6 border-b border-border bg-card/50 backdrop-blur-sm">
      <div className="flex items-center gap-6">
        <Logo />
      </div>

      <nav className="hidden md:flex items-center gap-2 rounded-full bg-secondary p-1">
        <NavItem href="/home">
          داشبورد
        </NavItem>
        <NavItem href="/classes">
          کلاس‌ها
        </NavItem>
        <NavItem href="/exam-prep">
          آمادگی آزمون
        </NavItem>
      </nav>

      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" className="h-10 w-10 rounded-full">
          <Bell className="h-5 w-5 text-text-muted" />
          <span className="sr-only">Notifications</span>
        </Button>
        <UserProfile />
      </div>
    </header>
  );
}
