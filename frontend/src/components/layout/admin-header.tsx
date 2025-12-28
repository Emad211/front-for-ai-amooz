'use client';

import { useState } from 'react';
import { usePathname } from 'next/navigation';
import { Menu } from 'lucide-react';
import { UserProfile } from '@/components/layout/user-profile';
import { Logo } from '@/components/ui/logo';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { SidebarContent } from './sidebar-content';

export function AdminHeader() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);

  // A simple way to get a readable title from the path
  const pageTitle = pathname.split('/').pop()?.replace(/-/g, ' ') || 'Dashboard';

  return (
    <header className="flex items-center justify-between gap-4">
      <div className="flex items-center gap-2 md:gap-4">
        {/* Mobile Menu Trigger */}
        <div className="lg:hidden">
          <Sheet open={isOpen} onOpenChange={setIsOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="h-10 w-10 rounded-xl bg-muted/50">
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="p-0 w-72 border-l-border">
              <SidebarContent onItemClick={() => setIsOpen(false)} />
            </SheetContent>
          </Sheet>
        </div>

        {/* Mobile Logo */}
        <div className="hidden sm:block lg:hidden">
          <Logo href="/admin" imageSize="sm" showText={false} />
        </div>
        
        <div className="flex items-center gap-2 text-lg md:text-xl font-black text-foreground">
          <span className="capitalize text-foreground">{pageTitle}</span>
        </div>
      </div>

      <div className="flex items-center gap-2 md:gap-3">
        <div className="flex items-center gap-1 md:gap-2">
          <UserProfile user={{
            name: 'مدیر سیستم',
            email: 'admin@example.com',
            avatar: '/avatars/admin.png'
          }} isAdmin={true} />
        </div>
      </div>
    </header>
  );
}
