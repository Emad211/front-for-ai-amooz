'use client';

import { TicketCard } from './ticket-card';
import type { Ticket } from '@/types';

interface TicketListProps {
  tickets: Ticket[];
  onTicketClick: (ticketId: string) => void;
  emptyMessage?: string;
}

export function TicketList({ tickets, onTicketClick, emptyMessage }: TicketListProps) {
  if (tickets.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">
          {emptyMessage || 'هیچ تیکتی یافت نشد'}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {tickets.map((ticket) => (
        <TicketCard
          key={ticket.id}
          ticket={ticket}
          onClick={onTicketClick}
        />
      ))}
    </div>
  );
}
