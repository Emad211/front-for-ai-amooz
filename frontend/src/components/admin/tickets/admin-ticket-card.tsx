'use client';

import { ChevronLeft, Clock, User } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { TicketStatusBadge, TicketPriorityBadge } from '@/components/shared/tickets';
import type { Ticket } from '@/constants/mock';

interface AdminTicketCardProps {
  ticket: Ticket;
  onClick: (ticketId: string) => void;
}

export function AdminTicketCard({ ticket, onClick }: AdminTicketCardProps) {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('fa-IR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <Card
      className="p-3 sm:p-4 hover:bg-muted/30 transition-colors cursor-pointer rounded-xl"
      onClick={() => onClick(ticket.id)}
    >
      <div className="flex items-start justify-between gap-3 sm:gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 sm:gap-2 mb-2 flex-wrap">
            <span className="text-[10px] sm:text-xs text-muted-foreground font-mono bg-muted/50 px-1.5 py-0.5 rounded">
              #{ticket.id}
            </span>
            <TicketStatusBadge status={ticket.status} />
            <TicketPriorityBadge priority={ticket.priority} />
          </div>
          
          <h3 className="font-medium text-sm sm:text-base text-foreground mb-2 truncate">
            {ticket.subject}
          </h3>
          
          {/* User Info */}
          <div className="flex items-center gap-2 mb-2">
            <User className="w-3 h-3 text-muted-foreground shrink-0" />
            <span className="text-[10px] sm:text-xs text-muted-foreground truncate">
              {ticket.userName} <span className="hidden xs:inline">({ticket.userEmail})</span>
            </span>
          </div>
          
          <div className="flex items-center gap-2 sm:gap-4 text-[10px] sm:text-xs text-muted-foreground flex-wrap">
            <span className="truncate">{ticket.department}</span>
            <span className="flex items-center gap-1 shrink-0">
              <Clock className="w-3 h-3" />
              {formatDate(ticket.updatedAt)}
            </span>
            <span className="shrink-0">{ticket.messages.length} پیام</span>
          </div>
        </div>
        
        <ChevronLeft className="w-4 h-4 sm:w-5 sm:h-5 text-muted-foreground shrink-0 mt-1" />
      </div>
    </Card>
  );
}
