'use client';

import { Button } from '@/components/ui/button';
import { ChevronLeft, Grid, History, Settings, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export function AdminHeader() {
  const pathname = usePathname();
  // A simple way to get a readable title from the path
  const pageTitle = pathname.split('/').pop()?.replace(/-/g, ' ') || 'Dashboard';

  return (
    <header className="flex items-center justify-between">
      <div className="flex items-center gap-2 text-xl font-bold text-foreground">
        <Link href="/admin" className="text-primary hover:underline text-lg">
          AI Amooz
        </Link>
        <ChevronLeft className="h-5 w-5 text-muted-foreground rotate-180" />
        <span className="capitalize text-lg text-muted-foreground">{pageTitle}</span>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outline" className="h-11 w-11 p-0 rounded-xl">
          <Grid className="h-5 w-5 text-muted-foreground" />
        </Button>
        <Button variant="outline" className="h-11 w-11 p-0 rounded-xl">
          <History className="h-5 w-5 text-muted-foreground" />
        </Button>
        <Button variant="outline" className="h-11 w-11 p-0 rounded-xl">
          <Settings className="h-5 w-5 text-muted-foreground" />
        </Button>
      </div>
    </header>
  );
}
