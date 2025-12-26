'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  ClipboardList,
  Users,
  Plus,
  Power,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const NavItem = ({ href, icon: Icon, children }) => {
  const pathname = usePathname();
  const isActive = pathname === href;

  return (
    <Link
      href={href}
      className={cn(
        'flex items-center gap-3 rounded-lg px-4 py-3 text-base font-medium transition-colors',
        isActive
          ? 'bg-primary/10 text-primary'
          : 'text-muted-foreground hover:text-foreground'
      )}
    >
      <Icon className="h-5 w-5" />
      {children}
    </Link>
  );
};

export function AdminSidebar() {
  return (
    <aside className="w-72 bg-card border-r border-border p-6 flex flex-col justify-between">
      <div>
        <h2 className="text-2xl font-bold text-foreground mb-10 text-right">Al amooz</h2>
        <nav className="flex flex-col gap-3">
          <NavItem href="/admin" icon={LayoutDashboard}>
            داشبورد
          </NavItem>
          <NavItem href="/admin/tasks" icon={ClipboardList}>
            لیست تسک ها
          </NavItem>
          <NavItem href="/admin/users" icon={Users}>
            مدیریت کاربران
          </NavItem>
          <Button asChild className="w-full h-12 text-base justify-center mt-4 bg-primary text-primary-foreground hover:bg-primary/90">
            <Link href="/admin/create-class">
              <Plus className="ml-2 h-5 w-5" />
              ایجاد کلاس مجازی
            </Link>
          </Button>
        </nav>
      </div>
      <div className="flex flex-col gap-2">
         <Button variant="ghost" className="w-full justify-end text-muted-foreground">
           غیرفعال
            <Power className="mr-2 h-5 w-5" />
         </Button>
      </div>
    </aside>
  );
}
