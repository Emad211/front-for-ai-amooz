'use client';

import { CheckCircle, User, Mail } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { Ticket, TicketStatus, TicketPriority } from '@/constants/mock';

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
    <div className="p-4 sm:p-5 border-b bg-card space-y-4">
      {/* Ticket Info */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-muted-foreground font-mono bg-muted/50 px-2 py-0.5 rounded">
            #{ticket.id}
          </span>
        </div>
        <h2 className="font-bold text-base sm:text-lg text-foreground leading-tight mb-2">
          {ticket.subject}
        </h2>
        
        {/* User Info */}
        <div className="flex flex-wrap items-center gap-3 text-xs sm:text-sm text-muted-foreground">
          <span className="flex items-center gap-1">
            <User className="w-3.5 h-3.5" />
            {ticket.userName}
          </span>
          <span className="flex items-center gap-1">
            <Mail className="w-3.5 h-3.5" />
            {ticket.userEmail}
          </span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-2 sm:gap-3">
        <Select value={ticket.status} onValueChange={(v) => onStatusChange(v as TicketStatus)}>
          <SelectTrigger className="w-[130px] sm:w-[150px] rounded-xl h-9 text-xs sm:text-sm">
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
          <SelectTrigger className="w-[110px] sm:w-[120px] rounded-xl h-9 text-xs sm:text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="low">کم</SelectItem>
            <SelectItem value="medium">متوسط</SelectItem>
            <SelectItem value="high">بالا</SelectItem>
          </SelectContent>
        </Select>

        {ticket.status !== 'closed' && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onStatusChange('closed')}
            className="rounded-xl gap-1.5 text-green-600 hover:text-green-600 h-9 text-xs sm:text-sm"
          >
            <CheckCircle className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            <span className="hidden xs:inline">بستن تیکت</span>
            <span className="xs:hidden">بستن</span>
          </Button>
        )}
      </div>
    </div>
  );
}
