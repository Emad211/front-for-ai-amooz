'use client';

import { AdminTicketCard } from './admin-ticket-card';
import type { Ticket } from '@/constants/mock';

interface AdminTicketListProps {
  tickets: Ticket[];
  onTicketClick: (ticketId: string) => void;
}

export function AdminTicketList({ tickets, onTicketClick }: AdminTicketListProps) {
  if (tickets.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">هیچ تیکتی یافت نشد</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {tickets.map((ticket) => (
        <AdminTicketCard
          key={ticket.id}
          ticket={ticket}
          onClick={onTicketClick}
        />
      ))}
    </div>
  );
}
