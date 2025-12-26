'use client';

import { Button } from '@/components/ui/button';
import { ChevronLeft, Grid, History, Settings, RefreshCw } from 'lucide-react';
import Link from 'next/link';

export function AdminHeader() {
  return (
    <header className="flex items-center justify-between pb-8">
      <div className="flex items-center gap-2 text-xl font-bold text-foreground">
        <Link href="/home" className="text-primary hover:underline">
          Al amooz
        </Link>
        <ChevronLeft className="h-5 w-5 text-muted-foreground" />
        <span>ایجاد کلاس مجازی جدید</span>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outline" className="h-11 w-11 p-0">
          <Grid className="h-5 w-5 text-muted-foreground" />
        </Button>
        <Button variant="outline" className="h-11 w-11 p-0">
          <History className="h-5 w-5 text-muted-foreground" />
        </Button>
        <Button variant="outline" className="h-11 w-11 p-0">
          <Settings className="h-5 w-5 text-muted-foreground" />
        </Button>
        <Button className="h-11 px-6 bg-primary text-primary-foreground hover:bg-primary/90">
            Share
        </Button>
      </div>
    </header>
  );
}
