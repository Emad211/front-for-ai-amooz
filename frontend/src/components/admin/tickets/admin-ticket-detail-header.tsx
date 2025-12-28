'use client';

import { CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { TicketStatusBadge, TicketPriorityBadge } from '@/components/shared/tickets';
import type { Ticket, TicketStatus, TicketPriority } from '@/constants/tickets-data';

interface AdminTicketDetailHeaderProps {
  ticket: Ticket;
  onClose: () => void;
  onStatusChange: (status: TicketStatus) => void;
  onPriorityChange: (priority: TicketPriority) => void;
}

export function AdminTicketDetailHeader({
  ticket,
  onClose,
  onStatusChange,
  onPriorityChange,
}: AdminTicketDetailHeaderProps) {
  return (
    <div className="p-4 border-b space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs text-muted-foreground font-mono">#{ticket.id}</span>
          </div>
          <h2 className="font-bold text-foreground">{ticket.subject}</h2>
          <p className="text-xs text-muted-foreground mt-1">
            {ticket.userName} • {ticket.userEmail}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Select value={ticket.status} onValueChange={(v) => onStatusChange(v as TicketStatus)}>
          <SelectTrigger className="w-[150px] rounded-xl h-9">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="open">باز</SelectItem>
            <SelectItem value="pending">در انتظار پاسخ</SelectItem>
            <SelectItem value="answered">پاسخ داده شده</SelectItem>
            <SelectItem value="closed">بسته شده</SelectItem>
          </SelectContent>
        </Select>

        <Select value={ticket.priority} onValueChange={(v) => onPriorityChange(v as TicketPriority)}>
          <SelectTrigger className="w-[120px] rounded-xl h-9">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="low">اولویت کم</SelectItem>
            <SelectItem value="medium">اولویت متوسط</SelectItem>
            <SelectItem value="high">اولویت بالا</SelectItem>
          </SelectContent>
        </Select>

        {ticket.status !== 'closed' && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onStatusChange('closed')}
            className="rounded-xl gap-1 text-green-600 hover:text-green-600"
          >
            <CheckCircle className="w-4 h-4" />
            بستن تیکت
          </Button>
        )}
      </div>
    </div>
  );
}
