'use client';

import { ChevronLeft, Clock } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { TicketStatusBadge, TicketPriorityBadge } from './ticket-badges';
import type { Ticket } from '@/constants/tickets-data';

interface TicketCardProps {
  ticket: Ticket;
  onClick: (ticketId: string) => void;
}

export function TicketCard({ ticket, onClick }: TicketCardProps) {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('fa-IR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
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
          
          <h3 className="font-medium text-sm sm:text-base text-foreground mb-1 truncate">
            {ticket.subject}
          </h3>
          
          <div className="flex items-center gap-3 sm:gap-4 text-[10px] sm:text-xs text-muted-foreground">
            <span className="truncate">{ticket.department}</span>
            <span className="flex items-center gap-1 shrink-0">
              <Clock className="w-3 h-3" />
              {formatDate(ticket.updatedAt)}
            </span>
          </div>
        </div>
        
        <ChevronLeft className="w-4 h-4 sm:w-5 sm:h-5 text-muted-foreground shrink-0 mt-1" />
      </div>
    </Card>
  );
}
