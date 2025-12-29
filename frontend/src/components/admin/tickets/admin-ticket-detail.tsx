'use client';

import { ScrollArea } from '@/components/ui/scroll-area';
import { AdminTicketDetailHeader } from './admin-ticket-detail-header';
import { TicketMessageBubble, TicketReplyInput } from '@/components/shared/tickets';
import type { Ticket, TicketStatus, TicketPriority } from '@/types';

interface AdminTicketDetailProps {
  ticket: Ticket;
  onClose: () => void;
  onReply: (ticketId: string, message: string) => void;
  onStatusChange: (ticketId: string, status: TicketStatus) => void;
  onPriorityChange: (ticketId: string, priority: TicketPriority) => void;
}

export function AdminTicketDetail({
  ticket,
  onClose,
  onReply,
  onStatusChange,
  onPriorityChange,
}: AdminTicketDetailProps) {
  const handleSendReply = (message: string) => {
    onReply(ticket.id, message);
  };

  return (
    <div className="flex flex-col h-full" dir="rtl">
      <AdminTicketDetailHeader
        ticket={ticket}
        onClose={onClose}
        onStatusChange={(status) => onStatusChange(ticket.id, status)}
        onPriorityChange={(priority) => onPriorityChange(ticket.id, priority)}
      />

      <ScrollArea className="flex-1">
        <div className="p-4 sm:p-5 space-y-4 sm:space-y-5">
          {ticket.messages.map((message) => (
            <TicketMessageBubble
              key={message.id}
              message={message}
              isOwnMessage={message.isAdmin}
            />
          ))}
        </div>
      </ScrollArea>

      {ticket.status !== 'closed' ? (
        <TicketReplyInput
          onSend={handleSendReply}
          placeholder="پاسخ به کاربر را بنویسید..."
        />
      ) : (
        <div className="p-4 border-t bg-muted/30 text-center">
          <p className="text-sm text-muted-foreground">این تیکت بسته شده است</p>
        </div>
      )}
    </div>
  );
}
