'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Bell, GraduationCap, LogOut } from 'lucide-react';

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const Logo = () => (
  <Link href="/" className="flex items-center gap-2">
    <GraduationCap className="h-7 w-7 text-primary" />
    <span className="text-xl font-bold text-text-light">AI-Amooz</span>
  </Link>
);

export function Header() {
  const pathname = usePathname();

  const navItems = [
    { href: '/', label: 'داشبورد' },
    { href: '/classes', label: 'کلاس‌ها' },
    { href: '/exam-prep', label: 'آمادگی آزمون' },
  ];

  return (
    <header className="flex items-center justify-between p-4 border-b border-border">
      <div className="flex items-center gap-8">
        <Logo />
      </div>

      <nav className="hidden md:flex items-center gap-1 bg-card/50 p-1 rounded-full border border-border">
        {navItems.map((item) => (
          <Button
            key={item.href}
            variant="ghost"
            className={cn(
              'rounded-full px-6 py-1 h-auto text-sm transition-all',
              pathname === item.href
                ? 'bg-card text-primary shadow-inner'
                : 'text-text-muted hover:text-text-light'
            )}
            asChild
          >
            <Link href={item.href}>{item.label}</Link>
          </Button>
        ))}
      </nav>

      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" className="relative text-text-muted">
          <Bell className="h-5 w-5" />
          <span className="absolute top-1.5 right-1.5 flex h-2 w-2">
            <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
          </span>
        </Button>
        <div className="flex items-center gap-3">
          <Avatar className="border-2 border-primary">
            <AvatarImage src="https://picsum.photos/seed/user/40/40" alt="Ali Rezaei" />
            <AvatarFallback>AR</AvatarFallback>
          </Avatar>
          <div className="text-right hidden sm:block">
            <p className="font-semibold text-sm text-text-light">علی رضایی</p>
            <p className="text-xs text-text-muted">دانش آموز</p>
          </div>
        </div>
        <Button variant="ghost" size="icon" className="text-text-muted">
          <LogOut className="h-5 w-5" />
        </Button>
      </div>
    </header>
  );
}
