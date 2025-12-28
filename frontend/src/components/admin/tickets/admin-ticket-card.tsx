'use client';

import { ChevronLeft, Clock, User } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { TicketStatusBadge, TicketPriorityBadge } from '@/components/shared/tickets';
import type { Ticket } from '@/constants/tickets-data';

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
      className="p-4 hover:bg-muted/30 transition-colors cursor-pointer rounded-xl"
      onClick={() => onClick(ticket.id)}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className="text-xs text-muted-foreground font-mono">
              #{ticket.id}
            </span>
            <TicketStatusBadge status={ticket.status} />
            <TicketPriorityBadge priority={ticket.priority} />
          </div>
          
          <h3 className="font-medium text-foreground mb-2 truncate">
            {ticket.subject}
          </h3>
          
          {/* User Info */}
          <div className="flex items-center gap-2 mb-2">
            <User className="w-3 h-3 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">
              {ticket.userName} ({ticket.userEmail})
            </span>
          </div>
          
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span>{ticket.department}</span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDate(ticket.updatedAt)}
            </span>
            <span>{ticket.messages.length} پیام</span>
          </div>
        </div>
        
        <ChevronLeft className="w-5 h-5 text-muted-foreground shrink-0" />
      </div>
    </Card>
  );
}
