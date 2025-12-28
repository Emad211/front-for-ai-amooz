'use client';

import { Plus, Ticket } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface TicketPageHeaderProps {
  onNewTicket: () => void;
}

export function TicketPageHeader({ onNewTicket }: TicketPageHeaderProps) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
      <div className="flex items-center gap-3">
        <div className="p-3 rounded-2xl bg-primary/10">
          <Ticket className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-foreground">تیکت‌های پشتیبانی</h1>
          <p className="text-sm text-muted-foreground">مشاهده و مدیریت درخواست‌های شما</p>
        </div>
      </div>

      <Button onClick={onNewTicket} className="rounded-xl gap-2">
        <Plus className="w-4 h-4" />
        تیکت جدید
      </Button>
    </div>
  );
}
